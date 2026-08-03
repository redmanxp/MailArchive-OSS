"""Bulk archive simulate + jobs."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from app.application.use_cases.accounts.account_use_cases import ArchiveSingleMessageUseCase
from app.config import Settings, get_settings
from app.domain.enums.jobs import ArchiveJobStatus
from app.domain.enums.roles import UserRole
from app.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.interfaces.mail_provider import MessageQuery
from app.domain.interfaces.repositories import IAuditLogRepository
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_repos import SqlAlchemyAuditLogRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure.storage.filesystem_storage import FilesystemMailStorage

logger = logging.getLogger(__name__)

_running_lock = threading.Lock()
_cancel_flags: dict[int, bool] = {}


def request_cancel(job_id: int) -> None:
    with _running_lock:
        _cancel_flags[job_id] = True


def _is_cancelled(job_id: int) -> bool:
    with _running_lock:
        return bool(_cancel_flags.get(job_id))


def _clear_cancel(job_id: int) -> None:
    with _running_lock:
        _cancel_flags.pop(job_id, None)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return None


def _build_query(criteria: dict[str, Any], *, limit: int) -> MessageQuery:
    folder_id = criteria.get("folder_id") or None
    older_days = criteria.get("older_than_days")
    older_than = None
    if older_days:
        older_than = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        older_than = older_than - timedelta(days=int(older_days))
    message_ids = criteria.get("message_ids") or []
    if isinstance(message_ids, str):
        message_ids = [message_ids]
    return MessageQuery(
        folder_ids=[folder_id] if folder_id else [],
        date_from=_parse_dt(criteria.get("date_from")),
        date_to=_parse_dt(criteria.get("date_to")),
        older_than=older_than if not message_ids else None,
        min_size_bytes=int(criteria["min_size_bytes"]) if criteria.get("min_size_bytes") and not message_ids else None,
        only_with_attachments=bool(criteria.get("only_with_attachments")) if not message_ids else False,
        message_ids=list(message_ids),
        limit=limit,
    )


class SimulateBulkArchiveUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
    ) -> None:
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        criteria: dict[str, Any],
        limit: int = 500,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede simular con esta cuenta")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            messages = provider.list_messages(_build_query(criteria, limit=max(1, min(limit, 2000))))
            total_bytes = sum(m.size_bytes or 0 for m in messages)
            items = [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "from_address": m.from_address,
                    "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                    "received_at": m.received_at.isoformat() if m.received_at else None,
                    "size_bytes": m.size_bytes or 0,
                    "has_attachments": m.has_attachments,
                    "folder": m.folder,
                }
                for m in messages
            ]
            return {
                "account_id": account_id,
                "message_count": len(messages),
                "total_bytes": total_bytes,
                "delete_after_archive": bool(criteria.get("delete_after_archive")),
                "messages": items,
                "sample": items[:20],
                "criteria": criteria,
            }
        finally:
            provider.disconnect()


class StartBulkArchiveUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        job_repo: SqlAlchemyArchiveJobRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
        audit_repo: IAuditLogRepository,
        settings: Settings,
    ) -> None:
        self.account_repo = account_repo
        self.job_repo = job_repo
        self.factory = factory
        self.cipher = cipher
        self.audit_repo = audit_repo
        self.settings = settings

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        criteria: dict[str, Any],
        delete_after_archive: bool = False,
        limit: int = 500,
        message_ids: list[str] | None = None,
    ) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede archivar")
        criteria_run = dict(criteria)
        if message_ids:
            criteria_run["message_ids"] = list(message_ids)
            limit = max(len(message_ids), 1)
        sim = SimulateBulkArchiveUseCase(self.account_repo, self.factory, self.cipher)
        preview = sim.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            account_id=account_id,
            criteria=criteria_run,
            limit=limit,
        )
        if message_ids:
            # Solo archivar los seleccionados (aunque la simulación haya listado más).
            id_set = set(message_ids)
            selected = [m for m in preview.get("messages") or [] if m["id"] in id_set]
            # Si Graph no re-listó por ids, usar tamaños del preview original vía criteria cache
            if not selected and message_ids:
                selected = [{"id": mid, "size_bytes": 0} for mid in message_ids]
            preview = {
                **preview,
                "message_count": len(message_ids),
                "total_bytes": sum(int(m.get("size_bytes") or 0) for m in selected),
                "messages": selected,
            }
        if preview["message_count"] == 0:
            raise ValidationError("No hay mensajes que coincidan con los criterios")

        criteria_store = dict(criteria)
        criteria_store["limit"] = limit
        criteria_store["folder_path"] = criteria.get("folder_path")
        if message_ids:
            criteria_store["message_ids"] = list(message_ids)

        job = self.job_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            account_id=account_id,
            criteria=criteria_store,
            delete_after_archive=delete_after_archive,
            total_messages=preview["message_count"],
            total_bytes=preview["total_bytes"],
            status=ArchiveJobStatus.PENDING.value,
        )
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="archive_job.create",
            resource_type="archive_job",
            resource_id=str(job.id),
            details={"message_count": preview["message_count"], "delete_after": delete_after_archive},
        )
        # Commit happens in request; start thread after flush
        job_id = job.id
        thread = threading.Thread(
            target=run_archive_job,
            args=(job_id, tenant_id),
            name=f"archive-job-{job_id}",
            daemon=True,
        )
        thread.start()
        logger.info("Started archive job id=%s tenant=%s count=%s", job_id, tenant_id, preview["message_count"])
        return {
            "id": job.id,
            "status": job.status,
            "total_messages": job.total_messages,
            "total_bytes": job.total_bytes,
            "delete_after_archive": job.delete_after_archive,
        }


def run_archive_job(job_id: int, tenant_id: int) -> None:
    """Background worker: archive messages for a job."""
    settings = get_settings()
    db = SessionLocal()
    try:
        job_repo = SqlAlchemyArchiveJobRepository(db)
        account_repo = SqlAlchemyMailAccountRepository(db)
        archived_repo = SqlAlchemyArchivedMailRepository(db)
        audit_repo = SqlAlchemyAuditLogRepository(db)
        cipher = CredentialCipher(settings)
        factory = MailProviderFactory(settings, cipher)
        storage = FilesystemMailStorage(settings.storage_root)

        job = job_repo.get(tenant_id, job_id)
        if job is None:
            return
        job_repo.update_progress(tenant_id, job_id, status=ArchiveJobStatus.RUNNING.value, started=True)
        db.commit()

        criteria = dict(job.criteria or {})
        limit = int(criteria.get("limit") or 500)
        folder_id = criteria.get("folder_id")
        folder_path = criteria.get("folder_path")
        message_ids = criteria.get("message_ids") or None
        if message_ids:
            limit = max(len(message_ids), 1)
        account = account_repo.get(tenant_id, job.account_id)
        if account is None:
            job_repo.update_progress(
                tenant_id,
                job_id,
                status=ArchiveJobStatus.FAILED.value,
                error_message="Cuenta no encontrada",
                finished=True,
            )
            db.commit()
            return

        def _persist(tokens: dict[str, Any]) -> None:
            account_repo.update_credentials(tenant_id, account.id, cipher.encrypt_dict(tokens))
            db.commit()

        provider = factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            messages = provider.list_messages(_build_query(criteria, limit=limit))
        finally:
            provider.disconnect()

        archive_uc = ArchiveSingleMessageUseCase(
            account_repo=account_repo,
            archived_repo=archived_repo,
            factory=factory,
            cipher=cipher,
            storage=storage,
            audit_repo=audit_repo,
        )

        processed = archived = skipped = failed = 0
        archived_bytes = 0
        role = UserRole.USER  # job owner acts as themselves; permission already checked
        # Use ADMIN for job execution against account ownership already validated
        try:
            from app.infrastructure.persistence.models import UserModel

            user_row = db.get(UserModel, job.user_id)
            if user_row:
                role = UserRole(user_row.role)
        except Exception:
            pass

        for msg in messages:
            if _is_cancelled(job_id):
                job_repo.update_progress(
                    tenant_id,
                    job_id,
                    status=ArchiveJobStatus.CANCELLED.value,
                    processed=processed,
                    archived=archived,
                    skipped=skipped,
                    failed=failed,
                    archived_bytes=archived_bytes,
                    finished=True,
                )
                db.commit()
                _clear_cancel(job_id)
                return

            processed += 1
            existing = archived_repo.get_by_provider_message_id(tenant_id, account.id, msg.id)
            if existing:
                skipped += 1
            else:
                try:
                    result = archive_uc.execute(
                        tenant_id=tenant_id,
                        user_id=job.user_id,
                        role=role,
                        account_id=account.id,
                        message_id=msg.id,
                        folder_id=folder_id,
                        folder_path=folder_path,
                        delete_after_archive=job.delete_after_archive,
                    )
                    archived += 1
                    archived_bytes += int(result.get("size_bytes") or msg.size_bytes or 0)
                except Exception as exc:
                    failed += 1
                    logger.exception("Job %s failed message %s: %s", job_id, msg.id, exc)

            if processed % 5 == 0 or processed == len(messages):
                job_repo.update_progress(
                    tenant_id,
                    job_id,
                    processed=processed,
                    archived=archived,
                    skipped=skipped,
                    failed=failed,
                    archived_bytes=archived_bytes,
                )
                db.commit()

        job_repo.update_progress(
            tenant_id,
            job_id,
            status=ArchiveJobStatus.COMPLETED.value,
            processed=processed,
            archived=archived,
            skipped=skipped,
            failed=failed,
            archived_bytes=archived_bytes,
            finished=True,
        )
        db.commit()
        logger.info(
            "Archive job %s done archived=%s skipped=%s failed=%s",
            job_id,
            archived,
            skipped,
            failed,
        )
    except Exception as exc:
        logger.exception("Archive job %s crashed", job_id)
        try:
            db.rollback()
            SqlAlchemyArchiveJobRepository(db).update_progress(
                tenant_id,
                job_id,
                status=ArchiveJobStatus.FAILED.value,
                error_message=str(exc)[:1000],
                finished=True,
            )
            db.commit()
        except Exception:
            logger.exception("Could not mark job failed")
    finally:
        _clear_cancel(job_id)
        db.close()


class CancelArchiveJobUseCase:
    def __init__(self, job_repo: SqlAlchemyArchiveJobRepository, audit_repo: IAuditLogRepository) -> None:
        self.job_repo = job_repo
        self.audit_repo = audit_repo

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, job_id: int) -> dict:
        job = self.job_repo.get(tenant_id, job_id)
        if job is None:
            raise NotFoundError("Job no encontrado")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and job.user_id != user_id:
            raise AuthorizationError("No puede cancelar este job")
        if job.status not in (ArchiveJobStatus.PENDING.value, ArchiveJobStatus.RUNNING.value):
            raise ValidationError(f"El job ya está en estado {job.status}")
        request_cancel(job_id)
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="archive_job.cancel",
            resource_type="archive_job",
            resource_id=str(job_id),
        )
        return {"id": job_id, "status": "cancelling"}
