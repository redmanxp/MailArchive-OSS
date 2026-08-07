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
from app.infrastructure.persistence.database import SessionLocal, commit_with_retry, write_with_retry
from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_repos import SqlAlchemyAuditLogRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.providers.imap_provider import ImapProvider
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure.storage.factory import build_mail_storage

logger = logging.getLogger(__name__)

_running_lock = threading.Lock()
_cancel_flags: dict[int, bool] = {}


def request_cancel(job_id: int) -> None:
    with _running_lock:
        _cancel_flags[job_id] = True


def clear_cancel(job_id: int) -> None:
    """Clear in-memory cancel flag (e.g. before retrying a job)."""
    with _running_lock:
        _cancel_flags.pop(job_id, None)


def _is_cancelled(job_id: int) -> bool:
    with _running_lock:
        return bool(_cancel_flags.get(job_id))


def _clear_cancel(job_id: int) -> None:
    clear_cancel(job_id)


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
        storage = build_mail_storage(settings)

        job = job_repo.try_claim(tenant_id, job_id)
        if job is None:
            # Already running, finished, or missing — avoid double execution.
            logger.info("Archive job id=%s tenant=%s not claimed (skip)", job_id, tenant_id)
            return
        commit_with_retry(db)

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
            commit_with_retry(db)
            return

        def _persist(tokens: dict[str, Any]) -> None:
            account_repo.update_credentials(tenant_id, account.id, cipher.encrypt_dict(tokens))
            commit_with_retry(db)

        provider = factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            messages = provider.list_messages(_build_query(criteria, limit=limit))
            seen_ids = {m.id for m in messages}
            # Historical backfill: fill remaining quota with older-than-cursor mail.
            if bool(criteria.get("historical_backfill")) and len(messages) < limit:
                remaining = limit - len(messages)
                backfill_before = _parse_dt(criteria.get("backfill_before"))
                if backfill_before is not None:
                    folder_id_bf = criteria.get("folder_id") or None
                    older_q = MessageQuery(
                        folder_ids=[folder_id_bf] if folder_id_bf else [],
                        older_than=backfill_before,
                        min_size_bytes=(
                            int(criteria["min_size_bytes"]) if criteria.get("min_size_bytes") else None
                        ),
                        only_with_attachments=bool(criteria.get("only_with_attachments")),
                        limit=remaining,
                    )
                    for msg in provider.list_messages(older_q):
                        if msg.id in seen_ids:
                            continue
                        messages.append(msg)
                        seen_ids.add(msg.id)
                        if len(messages) >= limit:
                            break
                    logger.info(
                        "Job %s historical backfill before=%s fetched_total=%s",
                        job_id,
                        backfill_before.isoformat(),
                        len(messages),
                    )
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
        max_received: datetime | None = None
        min_received: datetime | None = None
        min_backfill_received: datetime | None = None
        skipped_samples: list[dict[str, Any]] = []
        failed_samples: list[dict[str, Any]] = []
        archived_samples: list[dict[str, Any]] = []
        role = UserRole.USER  # job owner acts as themselves; permission already checked
        # Use ADMIN for job execution against account ownership already validated
        try:
            from app.infrastructure.persistence.models import UserModel

            user_row = db.get(UserModel, job.user_id)
            if user_row:
                role = UserRole(user_row.role)
        except Exception:
            pass

        def _persist_result(*, note: str | None = None) -> None:
            job_repo.set_result(
                tenant_id,
                job_id,
                {
                    "note": note,
                    "archived": archived,
                    "skipped_already_archived": skipped,
                    "failed": failed,
                    "archived_bytes": archived_bytes,
                    "skipped_samples": skipped_samples[:15],
                    "archived_samples": archived_samples[:15],
                    "failed_samples": failed_samples[:15],
                },
            )

        for msg in messages:
            if _is_cancelled(job_id):

                def _cancel_progress() -> None:
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
                    _persist_result(note="cancelled")

                write_with_retry(db, _cancel_progress)
                _notify_schedule(db, tenant_id, job.account_id, job_id, "cancelled", None, None, None)
                commit_with_retry(db)
                _clear_cancel(job_id)
                return

            processed += 1
            if msg.received_at:
                rt = msg.received_at
                if rt.tzinfo is None:
                    rt = rt.replace(tzinfo=UTC)
                if max_received is None or rt > max_received:
                    max_received = rt
                if min_received is None or rt < min_received:
                    min_received = rt
                bf_before = _parse_dt(criteria.get("backfill_before"))
                if bool(criteria.get("historical_backfill")) and (
                    bf_before is None or rt < bf_before
                ):
                    if min_backfill_received is None or rt < min_backfill_received:
                        min_backfill_received = rt
            existing = archived_repo.find_by_provider_message_ids(
                tenant_id,
                account.id,
                (
                    ImapProvider.message_id_aliases(msg.id, msg.folder)
                    if account.provider == "imap"
                    else [msg.id]
                ),
            )
            if existing:
                # Upgrade legacy plain IMAP UID → composite id when we skip.
                if (
                    account.provider == "imap"
                    and msg.id
                    and ImapProvider._ID_SEP in msg.id
                    and existing.provider_message_id != msg.id
                ):
                    clash = archived_repo.get_by_provider_message_id(
                        tenant_id, account.id, msg.id
                    )
                    if clash is None or clash.id == existing.id:
                        logger.info(
                            "Normalize provider_message_id mail=%s %r -> %r",
                            existing.id,
                            existing.provider_message_id,
                            msg.id,
                        )
                        existing.provider_message_id = msg.id
                        archived_repo._db.flush()
                skipped += 1
                if len(skipped_samples) < 15:
                    skipped_samples.append(
                        {
                            "message_id": msg.id,
                            "subject": (msg.subject or "")[:200],
                            "reason": "already_archived",
                        }
                    )
            else:
                try:
                    result = archive_uc.execute(
                        tenant_id=tenant_id,
                        user_id=job.user_id,
                        role=role,
                        account_id=account.id,
                        message_id=msg.id,
                        # Prefer per-message folder (all-folders scan); criteria folder is fallback.
                        folder_id=msg.folder or folder_id,
                        folder_path=msg.folder or folder_path,
                        delete_after_archive=job.delete_after_archive,
                    )
                    archived += 1
                    archived_bytes += int(result.get("size_bytes") or msg.size_bytes or 0)
                    if len(archived_samples) < 15:
                        archived_samples.append(
                            {
                                "message_id": msg.id,
                                "subject": (msg.subject or result.get("subject") or "")[:200],
                            }
                        )
                except Exception as exc:
                    failed += 1
                    logger.exception("Job %s failed message %s: %s", job_id, msg.id, exc)
                    if len(failed_samples) < 15:
                        failed_samples.append(
                            {
                                "message_id": msg.id,
                                "subject": (msg.subject or "")[:200],
                                "error": str(exc)[:500],
                            }
                        )

            # Commit every message so the SQLite write lock is not held across Graph I/O
            def _progress() -> None:
                job_repo.update_progress(
                    tenant_id,
                    job_id,
                    processed=processed,
                    archived=archived,
                    skipped=skipped,
                    failed=failed,
                    archived_bytes=archived_bytes,
                )

            write_with_retry(db, _progress)

        def _complete() -> None:
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
            _persist_result()

        write_with_retry(db, _complete)
        watermark = max_received or datetime.now(UTC)
        backfill_wm: datetime | None = None
        if bool(criteria.get("historical_backfill")):
            if min_backfill_received is not None:
                backfill_wm = min_backfill_received
            elif not criteria.get("backfill_before") and min_received is not None:
                backfill_wm = min_received
        _notify_schedule(
            db,
            tenant_id,
            job.account_id,
            job_id,
            "ok",
            None,
            watermark,
            backfill_wm,
        )
        commit_with_retry(db)
        logger.info(
            "Archive job %s done archived=%s skipped=%s failed=%s",
            job_id,
            archived,
            skipped,
            failed,
        )
    except Exception as exc:
        logger.exception("Archive job %s crashed", job_id)
        err_msg = str(exc)[:1000]
        crash_msg = str(exc)[:500]
        try:
            db.rollback()

            def _fail() -> None:
                SqlAlchemyArchiveJobRepository(db).update_progress(
                    tenant_id,
                    job_id,
                    status=ArchiveJobStatus.FAILED.value,
                    error_message=err_msg,
                    finished=True,
                )
                try:
                    SqlAlchemyArchiveJobRepository(db).set_result(
                        tenant_id,
                        job_id,
                        {
                            "note": "failed",
                            "archived": archived,
                            "skipped_already_archived": skipped,
                            "failed": failed,
                            "archived_bytes": archived_bytes,
                            "skipped_samples": skipped_samples[:15],
                            "archived_samples": archived_samples[:15],
                            "failed_samples": failed_samples[:15],
                            "crash": crash_msg,
                        },
                    )
                except NameError:
                    pass

            write_with_retry(db, _fail)
            try:
                job_row = SqlAlchemyArchiveJobRepository(db).get(tenant_id, job_id)
                if job_row:
                    _notify_schedule(
                        db, tenant_id, job_row.account_id, job_id, "failed", err_msg, None, None
                    )
                    commit_with_retry(db)
            except Exception:
                logger.exception("Could not update schedule after job failure")
        except Exception:
            logger.exception("Could not mark job failed")
    finally:
        _clear_cancel(job_id)
        db.close()


def _notify_schedule(
    db,
    tenant_id: int,
    account_id: int,
    job_id: int,
    status: str,
    error: str | None,
    watermark_at: datetime | None,
    backfill_watermark_at: datetime | None = None,
) -> None:
    try:
        from app.infrastructure.persistence.repositories.schedule_repo import (
            SqlAlchemyArchiveScheduleRepository,
        )

        SqlAlchemyArchiveScheduleRepository(db).mark_job_finished(
            tenant_id,
            account_id,
            job_id=job_id,
            status=status,
            error=error,
            watermark_at=watermark_at,
            backfill_watermark_at=backfill_watermark_at,
        )
    except Exception:
        logger.exception("Schedule notify failed account=%s job=%s", account_id, job_id)


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


class RetryArchiveJobUseCase:
    """Reset a failed/cancelled job to pending so it can run again with the same criteria."""

    def __init__(self, job_repo: SqlAlchemyArchiveJobRepository, audit_repo: IAuditLogRepository) -> None:
        self.job_repo = job_repo
        self.audit_repo = audit_repo

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, job_id: int) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede reintentar jobs")
        job = self.job_repo.get(tenant_id, job_id)
        if job is None:
            raise NotFoundError("Job no encontrado")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and job.user_id != user_id:
            raise AuthorizationError("No puede reintentar este job")
        if job.status not in (ArchiveJobStatus.FAILED.value, ArchiveJobStatus.CANCELLED.value):
            raise ValidationError("Solo se pueden reintentar jobs fallidos o cancelados")
        if self.job_repo.has_open_for_account(tenant_id, job.account_id):
            raise ValidationError("Ya hay un job pendiente o en curso para esta cuenta")
        previous_status = job.status
        account_id = job.account_id
        clear_cancel(job_id)
        reset = self.job_repo.reset_for_retry(tenant_id, job_id)
        if reset is None:
            raise ValidationError("No se pudo reiniciar el job")
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="archive_job.retry",
            resource_type="archive_job",
            resource_id=str(job_id),
            details={"account_id": account_id, "previous_status": previous_status},
        )
        logger.info("Archive job retry id=%s tenant=%s account=%s", job_id, tenant_id, account_id)
        return {"id": job_id, "status": ArchiveJobStatus.PENDING.value, "account_id": account_id}
