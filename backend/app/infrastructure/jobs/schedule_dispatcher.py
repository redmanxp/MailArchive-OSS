"""Enqueue due archive schedules as pending archive_jobs (incremental, not sync)."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from app.domain.enums.providers import AccountStatus

logger = logging.getLogger(__name__)

_started = False
_stop = threading.Event()


def start_schedule_dispatcher(*, poll_seconds: float = 30.0) -> None:
    global _started
    if _started:
        return
    _started = True
    _stop.clear()
    t = threading.Thread(
        target=_loop,
        args=(poll_seconds,),
        name="archive-schedule-dispatcher",
        daemon=True,
    )
    t.start()
    logger.info("Archive schedule dispatcher started (poll=%.1fs)", poll_seconds)


def stop_schedule_dispatcher() -> None:
    _stop.set()


def _loop(poll_seconds: float) -> None:
    from app.infrastructure.persistence.database import SessionLocal

    while not _stop.is_set():
        try:
            db = SessionLocal()
            try:
                _enqueue_due(db)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception:
            logger.exception("Schedule dispatcher loop error")
        _stop.wait(poll_seconds)


def _enqueue_due(db) -> int:
    from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
    from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyMailAccountRepository
    from app.infrastructure.persistence.repositories.schedule_repo import SqlAlchemyArchiveScheduleRepository

    schedules = SqlAlchemyArchiveScheduleRepository(db)
    jobs = SqlAlchemyArchiveJobRepository(db)
    accounts = SqlAlchemyMailAccountRepository(db)
    due = schedules.list_due(limit=20)
    created = 0
    for policy in due:
        account = accounts.get(policy.tenant_id, policy.account_id)
        if account is None:
            schedules.mark_job_finished(
                policy.tenant_id,
                policy.account_id,
                job_id=0,
                status="failed",
                error="Cuenta no encontrada",
            )
            # push next_run to avoid hot loop
            from datetime import timedelta

            policy.next_run_at = datetime.now(UTC) + timedelta(minutes=max(15, policy.interval_minutes))
            continue
        if account.status == AccountStatus.UNLINKED.value or not account.credentials_encrypted:
            schedules.mark_job_finished(
                policy.tenant_id,
                policy.account_id,
                job_id=0,
                status="skipped",
                error="Cuenta desvinculada o sin credenciales",
            )
            from datetime import timedelta

            policy.next_run_at = datetime.now(UTC) + timedelta(minutes=max(15, policy.interval_minutes))
            continue
        if jobs.has_open_for_account(policy.tenant_id, policy.account_id):
            # Busy: retry soon without advancing watermark
            from datetime import timedelta

            policy.next_run_at = datetime.now(UTC) + timedelta(minutes=5)
            policy.last_status = "skipped_busy"
            continue

        criteria: dict = {
            "source": "scheduled_incremental",
            "folder_id": policy.folder_id,
            "folder_path": policy.folder_path,
            "only_with_attachments": bool(policy.only_with_attachments),
            "limit": int(policy.limit_per_run or 500),
        }
        if policy.watermark_at is not None:
            criteria["date_from"] = policy.watermark_at.isoformat()

        job = jobs.create(
            tenant_id=policy.tenant_id,
            user_id=account.user_id,
            account_id=policy.account_id,
            criteria=criteria,
            delete_after_archive=False,
            total_messages=0,
            total_bytes=0,
            status="pending",
        )
        schedules.mark_enqueued(
            policy.tenant_id,
            policy.account_id,
            job_id=job.id,
            interval_minutes=policy.interval_minutes,
        )
        created += 1
        logger.info(
            "Scheduled incremental archive enqueued job=%s account=%s tenant=%s",
            job.id,
            policy.account_id,
            policy.tenant_id,
        )
    return created
