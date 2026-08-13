"""Bulk archive job endpoints."""

from __future__ import annotations

import threading
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user, map_domain_error
from app.application.use_cases.accounts.bulk_archive import (
    CancelArchiveJobUseCase,
    RetryArchiveJobUseCase,
    SimulateBulkArchiveUseCase,
    run_archive_job,
)
from app.config import Settings, get_settings
from app.domain.enums.jobs import ArchiveJobStatus
from app.domain.enums.roles import UserRole
from app.domain.exceptions import AuthorizationError, DomainError, NotFoundError, ValidationError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyMailAccountRepository
from app.infrastructure.persistence.repositories.sqlalchemy_repos import SqlAlchemyAuditLogRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.schemas.jobs import (
    ArchiveJobPublic,
    BulkSimulateRequest,
    BulkSimulateResponse,
    BulkStartRequest,
)

router = APIRouter(prefix="/archive/jobs", tags=["archive-jobs"])


def _cipher(settings: Settings) -> CredentialCipher:
    return CredentialCipher(settings)


def _account_emails(db: Session, tenant_id: int, account_ids: set[int]) -> dict[int, str]:
    if not account_ids:
        return {}
    out: dict[int, str] = {}
    for acc in SqlAlchemyMailAccountRepository(db).list_for_tenant(tenant_id):
        if acc.id in account_ids:
            out[acc.id] = acc.email
    return out


def _job_public(row, *, account_email: str | None = None) -> ArchiveJobPublic:
    criteria = dict(row.criteria or {}) if row.criteria else {}
    result = criteria.pop("__result", None) if isinstance(criteria, dict) else None
    # Hide internal result key from criteria exposed to clients
    public_criteria = {k: v for k, v in criteria.items() if k != "__result"} if criteria else None
    total = row.total_messages or 0
    processed = row.processed_messages or 0
    archived = row.archived_messages or 0
    # Scheduled/fill-quota: % is new archives vs limit, not listed messages (skips don't count).
    quota = bool(
        (public_criteria or {}).get("source") == "scheduled_incremental"
        or (public_criteria or {}).get("historical_backfill")
    )
    pct = round(((archived if quota else processed) / total) * 100, 1) if total else 0.0
    return ArchiveJobPublic(
        id=row.id,
        account_id=row.account_id,
        account_email=account_email,
        user_id=row.user_id,
        status=row.status,
        criteria=public_criteria or None,
        result=result if isinstance(result, dict) else None,
        delete_after_archive=row.delete_after_archive,
        total_messages=row.total_messages,
        processed_messages=row.processed_messages,
        archived_messages=row.archived_messages,
        skipped_messages=row.skipped_messages,
        failed_messages=row.failed_messages,
        total_bytes=row.total_bytes,
        archived_bytes=row.archived_bytes,
        error_message=row.error_message,
        started_at=row.started_at.isoformat() if row.started_at else None,
        finished_at=row.finished_at.isoformat() if row.finished_at else None,
        created_at=row.created_at.isoformat() if row.created_at else None,
        progress_pct=pct,
    )


@router.post("/simulate", response_model=BulkSimulateResponse)
def simulate_bulk(
    body: BulkSimulateRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BulkSimulateResponse:
    cipher = _cipher(settings)
    uc = SimulateBulkArchiveUseCase(
        SqlAlchemyMailAccountRepository(db),
        MailProviderFactory(settings, cipher),
        cipher,
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=body.account_id,
            criteria=body.criteria.model_dump(exclude_none=True),
            limit=body.limit,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return BulkSimulateResponse(**result)


@router.post("", response_model=ArchiveJobPublic)
def start_bulk(
    body: BulkStartRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArchiveJobPublic:
    if ctx.user.role == UserRole.READONLY:
        raise map_domain_error(AuthorizationError("Rol solo lectura: no puede archivar"))

    cipher = _cipher(settings)
    criteria = body.criteria.model_dump(exclude_none=True)
    message_ids = list(body.message_ids or [])
    if message_ids:
        criteria["message_ids"] = message_ids
        limit = max(len(message_ids), 1)
        total_messages = len(message_ids)
        total_bytes = int(body.total_bytes_hint or 0)
    else:
        sim = SimulateBulkArchiveUseCase(
            SqlAlchemyMailAccountRepository(db),
            MailProviderFactory(settings, cipher),
            cipher,
        )
        try:
            preview = sim.execute(
                tenant_id=ctx.user.tenant_id,
                user_id=ctx.user.id,
                role=ctx.user.role,
                account_id=body.account_id,
                criteria=criteria,
                limit=body.limit,
            )
        except DomainError as exc:
            raise map_domain_error(exc) from exc
        if preview["message_count"] == 0:
            raise map_domain_error(ValidationError("No hay mensajes que coincidan con los criterios"))
        limit = body.limit
        total_messages = preview["message_count"]
        total_bytes = preview["total_bytes"]

    if total_messages == 0:
        raise map_domain_error(ValidationError("No hay mensajes seleccionados para archivar"))

    # Validar acceso a la cuenta
    account = SqlAlchemyMailAccountRepository(db).get(ctx.user.tenant_id, body.account_id)
    if account is None:
        raise map_domain_error(NotFoundError("Cuenta no encontrada"))
    if ctx.user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != ctx.user.id:
        raise map_domain_error(AuthorizationError("No puede archivar con esta cuenta"))

    criteria_store = dict(criteria)
    criteria_store["limit"] = limit
    if message_ids:
        criteria_store["message_ids"] = message_ids
    job_repo = SqlAlchemyArchiveJobRepository(db)
    job = job_repo.create(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        account_id=body.account_id,
        criteria=criteria_store,
        delete_after_archive=body.delete_after_archive,
        total_messages=total_messages,
        total_bytes=total_bytes,
        status=ArchiveJobStatus.PENDING.value,
    )
    SqlAlchemyAuditLogRepository(db).add(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        action="archive_job.create",
        resource_type="archive_job",
        resource_id=str(job.id),
        details={"message_count": total_messages, "delete_after": body.delete_after_archive},
    )
    db.commit()
    job_id = job.id
    tenant_id = ctx.user.tenant_id
    threading.Thread(
        target=run_archive_job,
        args=(job_id, tenant_id),
        name=f"archive-job-{job_id}",
        daemon=True,
    ).start()
    job = job_repo.get(tenant_id, job_id)
    email = None
    if job is not None:
        acc = SqlAlchemyMailAccountRepository(db).get(tenant_id, job.account_id)
        email = acc.email if acc else None
    return _job_public(job, account_email=email)


@router.get("", response_model=list[ArchiveJobPublic])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> list[ArchiveJobPublic]:
    scope_user = None if ctx.user.role in (UserRole.ADMIN, UserRole.SUPERVISOR) else ctx.user.id
    rows = SqlAlchemyArchiveJobRepository(db).list_for_tenant(
        ctx.user.tenant_id, user_id=scope_user, limit=50
    )
    emails = _account_emails(db, ctx.user.tenant_id, {r.account_id for r in rows})
    return [_job_public(r, account_email=emails.get(r.account_id)) for r in rows]


@router.get("/{job_id}", response_model=ArchiveJobPublic)
def get_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> ArchiveJobPublic:
    row = SqlAlchemyArchiveJobRepository(db).get(ctx.user.tenant_id, job_id)
    if row is None:
        raise map_domain_error(NotFoundError("Job no encontrado"))
    if ctx.user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and row.user_id != ctx.user.id:
        raise map_domain_error(AuthorizationError("No puede ver este job"))
    acc = SqlAlchemyMailAccountRepository(db).get(ctx.user.tenant_id, row.account_id)
    return _job_public(row, account_email=acc.email if acc else None)


@router.post("/{job_id}/cancel", response_model=dict)
def cancel_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> dict:
    uc = CancelArchiveJobUseCase(
        SqlAlchemyArchiveJobRepository(db),
        SqlAlchemyAuditLogRepository(db),
    )
    try:
        return uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            job_id=job_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc


@router.post("/{job_id}/retry", response_model=ArchiveJobPublic)
def retry_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> ArchiveJobPublic:
    """Re-queue a failed or cancelled job with the same criteria."""
    job_repo = SqlAlchemyArchiveJobRepository(db)
    uc = RetryArchiveJobUseCase(job_repo, SqlAlchemyAuditLogRepository(db))
    try:
        uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            job_id=job_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    db.commit()
    tenant_id = ctx.user.tenant_id
    threading.Thread(
        target=run_archive_job,
        args=(job_id, tenant_id),
        name=f"archive-job-retry-{job_id}",
        daemon=True,
    ).start()
    job = job_repo.get(tenant_id, job_id)
    if job is None:
        raise map_domain_error(NotFoundError("Job no encontrado"))
    acc = SqlAlchemyMailAccountRepository(db).get(tenant_id, job.account_id)
    return _job_public(job, account_email=acc.email if acc else None)
