"""Admin endpoints — users, settings, audit."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import (
    CurrentUserContext,
    get_password_hasher,
    map_domain_error,
    require_roles,
)
from app.application.use_cases.users.departure import EmployeeDepartureUseCase
from app.application.use_cases.users.user_management import (
    CreateUserUseCase,
    DeactivateUserUseCase,
    GetSmtpSettingsUseCase,
    HardDeleteUserUseCase,
    ResetPasswordUseCase,
    RestoreUserUseCase,
    TestSmtpSettingsUseCase,
    UpdateSmtpSettingsUseCase,
    UpdateUserUseCase,
)
from app.infrastructure.persistence.repositories.schedule_repo import (
    SqlAlchemyArchiveScheduleRepository,
)
from app.config import Settings, get_settings, reload_settings
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import DomainError, ValidationError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import TenantModel
from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure import system_overrides
from app.schemas.admin import (
    CreateUserRequest,
    CreateUserResponse,
    DeactivateUserRequest,
    DepartureAccountItem,
    DeparturePreviewResponse,
    DepartureRequest,
    DepartureResponse,
    DepartureSkipItem,
    HardDeleteUserRequest,
    MicrosoftSettingsPublic,
    MicrosoftSettingsUpdate,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SmtpSettingsPublic,
    SmtpSettingsUpdate,
    SmtpTestRequest,
    SmtpTestResponse,
    SystemSettingsPublic,
    SystemSettingsUpdate,
    UpdateUserRequest,
    UserAdminPublic,
)
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditLogItem(BaseModel):
    id: int
    action: str
    user_id: int | None
    resource_type: str | None
    resource_id: str | None
    details: dict | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int = 0
    limit: int = 50
    offset: int = 0


def _settings_repo(db: Session, settings: Settings) -> SqlAlchemyTenantSettingsRepository:
    return SqlAlchemyTenantSettingsRepository(db, CredentialCipher(settings))


def _tenant_slug(db: Session, tenant_id: int) -> str:
    row = db.get(TenantModel, tenant_id)
    return row.slug if row else "acme"


@router.get("/users", response_model=list[UserAdminPublic])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    deleted: Annotated[bool, Query(description="List soft-deleted users only")] = False,
) -> list[UserAdminPublic]:
    users = SqlAlchemyUserRepository(db).list_by_tenant(ctx.user.tenant_id, only_deleted=deleted)
    return [
        UserAdminPublic(
            id=u.id,
            tenant_id=u.tenant_id,
            name=u.name,
            email=u.email,
            role=u.role.value,
            status=u.status.value,
            must_change_password=u.must_change_password,
        )
        for u in users
    ]


@router.post("/users", response_model=CreateUserResponse)
def create_user(
    body: CreateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CreateUserResponse:
    try:
        role = UserRole(body.role)
    except ValueError as exc:
        raise map_domain_error(ValidationError(f"Rol inválido: {body.role}")) from exc
    uc = CreateUserUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings_repo=_settings_repo(db, settings),
        settings=settings,
        tenant_slug=_tenant_slug(db, ctx.user.tenant_id),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            name=body.name,
            email=str(body.email),
            role=role,
            password=body.password,
            must_change_password=body.must_change_password if body.password else True,
            send_welcome_email=body.send_welcome_email,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return CreateUserResponse(**result)


@router.patch("/users/{user_id}", response_model=UserAdminPublic)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> UserAdminPublic:
    try:
        role = UserRole(body.role) if body.role else None
        status = UserStatus(body.status) if body.status else None
    except ValueError as exc:
        raise map_domain_error(ValidationError(str(exc))) from exc
    uc = UpdateUserUseCase(SqlAlchemyUserRepository(db), SqlAlchemyAuditLogRepository(db))
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            name=body.name,
            role=role,
            status=status,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return UserAdminPublic(
        id=result["id"],
        tenant_id=ctx.user.tenant_id,
        name=result["name"],
        email=result["email"],
        role=result["role"],
        status=result["status"],
        must_change_password=result["must_change_password"],
    )


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResetPasswordResponse:
    uc = ResetPasswordUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings_repo=_settings_repo(db, settings),
        settings=settings,
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            new_password=body.new_password,
            must_change_password=body.must_change_password if body.new_password else True,
            send_email=body.send_email,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ResetPasswordResponse(**result)


def _departure_uc(
    db: Session, settings: Settings
) -> EmployeeDepartureUseCase:
    return EmployeeDepartureUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings=settings,
        cipher=CredentialCipher(settings),
        job_repo=SqlAlchemyArchiveJobRepository(db),
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        schedule_repo=SqlAlchemyArchiveScheduleRepository(db),
    )


@router.get("/users/{user_id}/departure", response_model=DeparturePreviewResponse)
def departure_preview(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeparturePreviewResponse:
    """Preview employee departure wizard (user + linked accounts)."""
    try:
        result = _departure_uc(db, settings).preview(
            tenant_id=ctx.user.tenant_id, user_id=user_id
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    u = result["user"]
    return DeparturePreviewResponse(
        user=UserAdminPublic(
            id=u["id"],
            tenant_id=ctx.user.tenant_id,
            name=u["name"],
            email=u["email"],
            role=u["role"],
            status=u["status"],
            must_change_password=bool(u.get("must_change_password", False)),
        ),
        accounts=[DepartureAccountItem(**a) for a in result["accounts"]],
    )


@router.post("/users/{user_id}/departure", response_model=DepartureResponse)
def employee_departure(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
    body: DepartureRequest | None = None,
) -> DepartureResponse:
    """Archive (optional) + disable schedules + transfer/unlink accounts + deactivate user."""
    payload = body or DepartureRequest()
    try:
        result = _departure_uc(db, settings).execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            actor_role=ctx.user.role,
            user_id=user_id,
            accounts_action=payload.accounts_action,
            transfer_to_user_id=payload.transfer_to_user_id,
            archive_enabled=payload.archive_enabled,
            older_than_days=payload.older_than_days,
            archive_limit=payload.archive_limit,
            disable_schedules=payload.disable_schedules,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return DepartureResponse(
        user_id=result["user_id"],
        email=result["email"],
        deactivated=bool(result["deactivated"]),
        accounts_action=str(result["accounts_action"]),
        accounts_touched=int(result["accounts_touched"] or 0),
        mails_reassigned=int(result.get("mails_reassigned") or 0),
        job_ids=list(result.get("job_ids") or []),
        archive_skipped=[DepartureSkipItem(**s) for s in (result.get("archive_skipped") or [])],
        schedules_disabled=int(result.get("schedules_disabled") or 0),
    )


@router.post("/users/{user_id}/deactivate", response_model=MessageResponse)
def deactivate_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    body: DeactivateUserRequest | None = None,
) -> MessageResponse:
    uc = DeactivateUserUseCase(
        SqlAlchemyUserRepository(db),
        SqlAlchemyAuditLogRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        job_repo=SqlAlchemyArchiveJobRepository(db),
    )
    payload = body or DeactivateUserRequest()
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            accounts_action=payload.accounts_action,
            transfer_to_user_id=payload.transfer_to_user_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    action = result.get("accounts_action", "unlink")
    n = result.get("accounts_touched", 0)
    return MessageResponse(
        message=f"Usuario desactivado ({action}, {n} cuenta(s))"
    )


@router.post("/users/{user_id}/restore", response_model=UserAdminPublic)
def restore_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> UserAdminPublic:
    uc = RestoreUserUseCase(SqlAlchemyUserRepository(db), SqlAlchemyAuditLogRepository(db))
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return UserAdminPublic(
        id=result["id"],
        tenant_id=ctx.user.tenant_id,
        name=result["name"],
        email=result["email"],
        role=result["role"],
        status=result["status"],
        must_change_password=result["must_change_password"],
    )


@router.post("/users/{user_id}/hard-delete", response_model=MessageResponse)
def hard_delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    body: HardDeleteUserRequest | None = None,
) -> MessageResponse:
    payload = body or HardDeleteUserRequest()
    uc = HardDeleteUserUseCase(
        SqlAlchemyUserRepository(db),
        SqlAlchemyAuditLogRepository(db),
        SqlAlchemyRefreshTokenRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        job_repo=SqlAlchemyArchiveJobRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            reassign_to_user_id=payload.reassign_to_user_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    n = result.get("accounts_reassigned", 0)
    return MessageResponse(
        message=f"Usuario {result['email']} eliminado definitivamente ({n} cuenta(s) reasignadas)"
    )


@router.get("/settings/smtp", response_model=SmtpSettingsPublic)
def get_smtp_settings(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpSettingsPublic:
    from app.infrastructure.email.templates import default_email_templates, list_available_locales

    data = GetSmtpSettingsUseCase(_settings_repo(db, settings)).execute(ctx.user.tenant_id)
    defaults = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "from_email": settings.smtp_from or settings.smtp_user,
        "from_name": settings.app_name,
        "reply_to": settings.smtp_reply_to,
        "timeout_seconds": settings.smtp_timeout_seconds,
        "starttls": settings.smtp_tls,
        "enabled": bool(settings.smtp_host),
        "configured": bool(settings.smtp_host and settings.smtp_user),
        "email_templates": default_email_templates(),
    }
    merged = {**defaults, **data}
    if not merged.get("email_templates"):
        merged["email_templates"] = default_email_templates()
    merged["available_locales"] = list_available_locales()
    return SmtpSettingsPublic(**merged)


@router.get("/settings/system", response_model=SystemSettingsPublic)
def get_system_settings(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemSettingsPublic:
    view = system_overrides.public_system_view(settings)
    view["tenant_count"] = len(SqlAlchemyTenantRepository(db).list_all())
    return SystemSettingsPublic(**view)


@router.put("/settings/system", response_model=SystemSettingsPublic)
def update_system_settings(
    body: SystemSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemSettingsPublic:
    from fastapi import HTTPException

    payload = body.model_dump(exclude_unset=True)
    engine = payload.get("db_engine")
    if engine is not None and engine not in ("sqlite", "mysql"):
        raise HTTPException(status_code=400, detail="db_engine must be sqlite or mysql")
    if "storage_backend" in payload and payload["storage_backend"] is not None:
        backend = str(payload["storage_backend"]).strip().lower()
        if backend not in ("filesystem", "s3", "minio", "object"):
            raise HTTPException(status_code=400, detail="storage_backend must be filesystem or s3")
        payload["storage_backend"] = "s3" if backend in ("s3", "minio", "object") else "filesystem"
    for s3_key in (
        "s3_endpoint_url",
        "s3_access_key",
        "s3_secret_key",
        "s3_bucket",
        "s3_region",
        "s3_prefix",
    ):
        if s3_key in payload and isinstance(payload[s3_key], str):
            payload[s3_key] = payload[s3_key].strip()
    if "tenant_mode" in payload:
        mode = system_overrides.normalize_tenant_mode(payload.get("tenant_mode"))
        if mode == "single":
            count = len(SqlAlchemyTenantRepository(db).list_all())
            if count > 1:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No se puede activar modo single: hay {count} organizaciones. "
                        "Dejá solo una o usá modo multi."
                    ),
                )
        payload["tenant_mode"] = mode
    system_overrides.update_system_overrides(settings, payload)
    reload_settings()
    view = system_overrides.public_system_view(get_settings())
    view["tenant_count"] = len(SqlAlchemyTenantRepository(db).list_all())
    return SystemSettingsPublic(**view)


@router.get("/settings/microsoft", response_model=MicrosoftSettingsPublic)
def get_microsoft_settings(
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MicrosoftSettingsPublic:
    return MicrosoftSettingsPublic(**system_overrides.public_microsoft_view(settings))


@router.put("/settings/microsoft", response_model=MicrosoftSettingsPublic)
def update_microsoft_settings(
    body: MicrosoftSettingsUpdate,
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MicrosoftSettingsPublic:
    payload = body.model_dump(exclude_unset=True)
    # Map API names to override keys
    mapped: dict = {}
    if "client_id" in payload:
        mapped["microsoft_client_id"] = payload["client_id"]
    if "tenant_id" in payload:
        mapped["microsoft_tenant_id"] = payload["tenant_id"]
    if "redirect_uri" in payload:
        # Azure requires exact match; strip accidental spaces from the Settings field
        mapped["microsoft_redirect_uri"] = (payload["redirect_uri"] or "").strip()
    if "client_secret" in payload:
        mapped["microsoft_client_secret"] = payload["client_secret"]
    system_overrides.update_microsoft_overrides(settings, mapped)
    reload_settings()
    return MicrosoftSettingsPublic(**system_overrides.public_microsoft_view(get_settings()))


@router.put("/settings/smtp", response_model=SmtpSettingsPublic)
def update_smtp_settings(
    body: SmtpSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpSettingsPublic:
    from app.infrastructure.email.templates import default_email_templates, list_available_locales

    uc = UpdateSmtpSettingsUseCase(_settings_repo(db, settings), SqlAlchemyAuditLogRepository(db))
    payload = body.model_dump(exclude_unset=True)
    result = uc.execute(tenant_id=ctx.user.tenant_id, actor_user_id=ctx.user.id, payload=payload)
    defaults = {
        "host": "",
        "port": 587,
        "user": "",
        "from_email": "",
        "from_name": "MailArchive",
        "starttls": True,
        "enabled": True,
        "configured": False,
        "email_templates": default_email_templates(),
    }
    merged = {**defaults, **result}
    merged["available_locales"] = list_available_locales()
    return SmtpSettingsPublic(**merged)


@router.post("/settings/smtp/test", response_model=SmtpTestResponse)
def test_smtp_settings(
    body: SmtpTestRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpTestResponse:
    uc = TestSmtpSettingsUseCase(_settings_repo(db, settings), settings)
    payload = body.model_dump(exclude_unset=True) if body else None
    result = uc.execute(ctx.user.tenant_id, payload if (payload and payload.get("host")) else None)
    return SmtpTestResponse(**result)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    rows, total = SqlAlchemyAuditLogRepository(db).search(
        ctx.user.tenant_id, q=q, limit=limit, offset=offset
    )
    return AuditLogListResponse(
        items=[
            AuditLogItem(
                id=r.id,
                action=r.action,
                user_id=r.user_id,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                details=r.details,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/audit-logs", response_model=MessageResponse)
def clear_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> MessageResponse:
    repo = SqlAlchemyAuditLogRepository(db)
    deleted = repo.delete_all_for_tenant(ctx.user.tenant_id)
    repo.add(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        action="audit.clear_all",
        resource_type="audit_logs",
        details={"deleted": deleted},
    )
    return MessageResponse(message=f"Se borraron {deleted} registros de auditoría.")
