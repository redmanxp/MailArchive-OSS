"""Bulk archive simulate + jobs."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from app.application.use_cases.accounts.account_use_cases import ArchiveSingleMessageUseCase
from app.config import Settings, get_settings
from app.domain.enums.jobs import ArchiveJobStatus
from app.domain.enums.providers import MailProviderType
from app.domain.enums.roles import UserRole
from app.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.interfaces.mail_provider import MessageQuery, MessageSummary
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


_FILL_PAGE = 500
_FILL_MAX_PAGES = 40


def _aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _received_utc(msg: MessageSummary) -> datetime | None:
    return _aware_utc(msg.received_at)


def _batch_min_received(msgs: list[MessageSummary]) -> datetime | None:
    times = [t for t in (_received_utc(m) for m in msgs) if t is not None]
    return min(times) if times else None


def _page_query(
    criteria: dict[str, Any],
    *,
    limit: int,
    date_from: datetime | None = None,
    older_than: datetime | None = None,
) -> MessageQuery:
    folder_id = criteria.get("folder_id") or None
    return MessageQuery(
        folder_ids=[folder_id] if folder_id else [],
        date_from=date_from,
        date_to=_parse_dt(criteria.get("date_to")),
        older_than=older_than,
        min_size_bytes=int(criteria["min_size_bytes"]) if criteria.get("min_size_bytes") else None,
        only_with_attachments=bool(criteria.get("only_with_attachments")),
        limit=limit,
    )


def _dedup_ids(account: Any, msg: MessageSummary) -> list[str]:
    if account.provider == MailProviderType.IMAP.value:
        return ImapProvider.message_id_aliases(msg.id, msg.folder)
    return [msg.id]


def _note_skip_existing(
    archived_repo: SqlAlchemyArchivedMailRepository,
    tenant_id: int,
    account: Any,
    msg: MessageSummary,
) -> str | None:
    """Return skip reason or None if the message should be archived."""
    ids = _dedup_ids(account, msg)
    existing = archived_repo.find_by_provider_message_ids(tenant_id, account.id, ids)
    excluded = archived_repo.is_excluded(tenant_id, account.id, provider_message_ids=ids)
    if (
        existing
        and account.provider == MailProviderType.IMAP.value
        and msg.id
        and ImapProvider._ID_SEP in msg.id
        and existing.provider_message_id != msg.id
    ):
        clash = archived_repo.get_by_provider_message_id(tenant_id, account.id, msg.id)
        if clash is None or clash.id == existing.id:
            logger.info(
                "Normalize provider_message_id mail=%s %r -> %r",
                existing.id,
                existing.provider_message_id,
                msg.id,
            )
            existing.provider_message_id = msg.id
            archived_repo._db.flush()
    if excluded and not existing:
        return "excluded"
    if existing or excluded:
        return "already_archived"
    return None


def _scan_fill_quota(
    *,
    provider: Any,
    archived_repo: SqlAlchemyArchivedMailRepository,
    tenant_id: int,
    account: Any,
    criteria: dict[str, Any],
    limit: int,
    job_id: int,
    on_progress: Any,
) -> dict[str, Any]:
    """Collect up to `limit` not-yet-archived messages. Skips do not consume the quota."""
    page_size = min(max(limit, 1), _FILL_PAGE)
    seen_ids: set[str] = set()
    to_archive: list[MessageSummary] = []
    skipped = 0
    skipped_samples: list[dict[str, Any]] = []
    scanned = 0
    max_received: datetime | None = None
    min_received: datetime | None = None
    min_backfill_received: datetime | None = None
    bf_before = _parse_dt(criteria.get("backfill_before"))
    historical = bool(criteria.get("historical_backfill"))

    def _track_received(msg: MessageSummary, *, backfill: bool) -> None:
        nonlocal max_received, min_received, min_backfill_received
        rt = _received_utc(msg)
        if rt is None:
            return
        if max_received is None or rt > max_received:
            max_received = rt
        if min_received is None or rt < min_received:
            min_received = rt
        if historical and (backfill or bf_before is None or rt < bf_before):
            if min_backfill_received is None or rt < min_backfill_received:
                min_backfill_received = rt

    def _consume_page(batch: list[MessageSummary], *, backfill: bool) -> list[MessageSummary]:
        nonlocal skipped, scanned
        fresh = [m for m in batch if m.id and m.id not in seen_ids]
        for msg in fresh:
            seen_ids.add(msg.id)
            scanned += 1
            _track_received(msg, backfill=backfill)
            reason = _note_skip_existing(archived_repo, tenant_id, account, msg)
            if reason:
                skipped += 1
                if len(skipped_samples) < 15:
                    skipped_samples.append(
                        {"message_id": msg.id, "subject": (msg.subject or "")[:200], "reason": reason}
                    )
                continue
            to_archive.append(msg)
            if len(to_archive) >= limit:
                break
        return fresh

    def _list_pages(*, date_from: datetime | None, older_than: datetime | None, backfill: bool, label: str) -> bool:
        cursor = older_than
        for page_no in range(1, _FILL_MAX_PAGES + 1):
            if _is_cancelled(job_id) or len(to_archive) >= limit:
                return False
            batch = provider.list_messages(
                _page_query(criteria, limit=page_size, date_from=date_from, older_than=cursor)
            )
            fresh = _consume_page(batch, backfill=backfill)
            logger.info(
                "Job %s %s page=%s fetched=%s fresh=%s queued=%s skipped=%s cursor=%s",
                job_id,
                label,
                page_no,
                len(batch),
                len(fresh),
                len(to_archive),
                skipped,
                cursor.isoformat() if cursor else None,
            )
            on_progress(scanned=scanned, skipped=skipped, queued=len(to_archive))
            if not fresh:
                return True
            if len(to_archive) >= limit:
                return False
            batch_min = _batch_min_received(fresh)
            if batch_min is None:
                return True
            if cursor is not None and batch_min >= cursor:
                return True
            cursor = batch_min
            if len(fresh) < page_size:
                return True
        logger.warning("Job %s %s hit max pages=%s scanned=%s", job_id, label, _FILL_MAX_PAGES, scanned)
        return True

    date_from = _parse_dt(criteria.get("date_from"))
    forward_exhausted = _list_pages(date_from=date_from, older_than=None, backfill=False, label="forward")
    backfill_exhausted = False
    if historical and len(to_archive) < limit and not _is_cancelled(job_id):
        if bf_before is None and min_received is not None:
            bf_before = min_received
        if bf_before is not None:
            logger.info(
                "Job %s historical backfill remaining=%s before=%s forward_exhausted=%s",
                job_id,
                limit - len(to_archive),
                bf_before.isoformat(),
                forward_exhausted,
            )
            backfill_exhausted = _list_pages(
                date_from=None, older_than=bf_before, backfill=True, label="backfill"
            )
        else:
            logger.info("Job %s historical backfill skipped (no backfill_before yet)", job_id)
            backfill_exhausted = True
    elif not historical:
        backfill_exhausted = True

    if forward_exhausted and (not historical or backfill_exhausted) and len(to_archive) == 0:
        logger.info(
            "Job %s mailbox window empty scanned=%s skipped=%s (no more mail to archive)",
            job_id,
            scanned,
            skipped,
        )

    return {
        "messages": to_archive,
        "skipped": skipped,
        "skipped_samples": skipped_samples,
        "scanned": scanned,
        "max_received": max_received,
        "min_received": min_received,
        "min_backfill_received": min_backfill_received,
        "cancelled": _is_cancelled(job_id),
        "forward_exhausted": forward_exhausted,
        "backfill_exhausted": backfill_exhausted,
    }


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

        criteria = dict(job.criteria or {})
        limit = int(criteria.get("limit") or 500)
        folder_id = criteria.get("folder_id")
        folder_path = criteria.get("folder_path")
        message_ids = criteria.get("message_ids") or None
        if message_ids:
            limit = max(len(message_ids), 1)
        fill_quota_job = (not message_ids) and (
            bool(criteria.get("historical_backfill"))
            or criteria.get("source") == "scheduled_incremental"
        )
        if fill_quota_job and not (job.total_messages or 0):
            job.total_messages = limit
        commit_with_retry(db)
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
        fill_quota = (not message_ids) and (
            bool(criteria.get("historical_backfill"))
            or criteria.get("source") == "scheduled_incremental"
        )

        processed = archived = skipped = failed = 0
        archived_bytes = 0
        max_received: datetime | None = None
        min_received: datetime | None = None
        min_backfill_received: datetime | None = None
        skipped_samples: list[dict[str, Any]] = []
        failed_samples: list[dict[str, Any]] = []
        archived_samples: list[dict[str, Any]] = []

        def _scan_progress(*, scanned: int, skipped: int, queued: int) -> None:
            def _p() -> None:
                job_repo.update_progress(
                    tenant_id,
                    job_id,
                    processed=scanned,
                    archived=0,
                    skipped=skipped,
                    failed=0,
                    archived_bytes=0,
                )

            write_with_retry(db, _p)

        provider.connect()
        try:
            if fill_quota:
                scan = _scan_fill_quota(
                    provider=provider,
                    archived_repo=archived_repo,
                    tenant_id=tenant_id,
                    account=account,
                    criteria=criteria,
                    limit=limit,
                    job_id=job_id,
                    on_progress=_scan_progress,
                )
                messages = scan["messages"]
                skipped = int(scan["skipped"])
                skipped_samples = list(scan["skipped_samples"])
                processed = skipped
                max_received = scan["max_received"]
                min_received = scan["min_received"]
                min_backfill_received = scan["min_backfill_received"]
                logger.info(
                    "Job %s fill-quota queued=%s skipped=%s scanned=%s forward_done=%s backfill_done=%s",
                    job_id,
                    len(messages),
                    skipped,
                    scan["scanned"],
                    scan["forward_exhausted"],
                    scan["backfill_exhausted"],
                )
            else:
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
            provider_ids = (
                ImapProvider.message_id_aliases(msg.id, msg.folder)
                if account.provider == MailProviderType.IMAP.value
                else [msg.id]
            )
            existing = archived_repo.find_by_provider_message_ids(
                tenant_id,
                account.id,
                provider_ids,
            )
            excluded = archived_repo.is_excluded(
                tenant_id,
                account.id,
                provider_message_ids=provider_ids,
            )
            if excluded or existing:
                # Upgrade legacy plain IMAP UID → composite id when we skip.
                if (
                    existing
                    and account.provider == MailProviderType.IMAP.value
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
                            "reason": "excluded" if excluded and not existing else "already_archived",
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
                        internet_message_id=msg.internet_message_id,
                        from_address=msg.from_address,
                        subject=msg.subject,
                        sent_at=msg.sent_at,
                    )
                    if result.get("excluded") or result.get("already_archived"):
                        skipped += 1
                        if len(skipped_samples) < 15:
                            skipped_samples.append(
                                {
                                    "message_id": msg.id,
                                    "subject": (msg.subject or result.get("subject") or "")[:200],
                                    "reason": (
                                        "excluded"
                                        if result.get("excluded")
                                        else "already_archived"
                                    ),
                                }
                            )
                    else:
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
            note = None
            if fill_quota and archived == 0 and not messages:
                note = "no_pending_mail"
            _persist_result(note=note)

        write_with_retry(db, _complete)
        # fill-quota empty scan: do not invent "now" or we skip real mail on the next run
        watermark = max_received if (max_received is not None or fill_quota) else datetime.now(UTC)
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
