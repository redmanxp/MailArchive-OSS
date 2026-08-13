"""Enqueue due archive schedules as pending archive_jobs (incremental, not sync)."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

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
                from app.infrastructure.persistence.database import commit_with_retry

                commit_with_retry(db)
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception:
            logger.exception("Schedule dispatcher loop error")
        _stop.wait(poll_seconds)


def enqueue_account_schedule_now(db: Any, tenant_id: int, account_id: int) -> int:
    """Enqueue one scheduled incremental job immediately. Returns job id."""
    from app.domain.exceptions import NotFoundError, ValidationError
    from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
    from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyMailAccountRepository
    from app.infrastructure.persistence.repositories.schedule_repo import SqlAlchemyArchiveScheduleRepository

    schedules = SqlAlchemyArchiveScheduleRepository(db)
    jobs = SqlAlchemyArchiveJobRepository(db)
    accounts = SqlAlchemyMailAccountRepository(db)

    policy = schedules.get_by_account(tenant_id, account_id)
    if policy is None or not policy.enabled:
        raise ValidationError("Activá el archivo programado antes de ejecutarlo")

    account = accounts.get(tenant_id, account_id)
    if account is None:
        raise NotFoundError("Cuenta no encontrada")
    if account.status == AccountStatus.UNLINKED.value or not account.credentials_encrypted:
        raise ValidationError("La cuenta no tiene credenciales para archivar")
    if jobs.has_open_for_account(tenant_id, account_id):
        raise ValidationError("Ya hay un job pendiente o en curso para esta cuenta")

    job_id = _enqueue_one(schedules, jobs, account, policy)
    logger.info(
        "Schedule run-now enqueued job=%s account=%s tenant=%s",
        job_id,
        account_id,
        tenant_id,
    )
    return job_id


def _enqueue_one(schedules: Any, jobs: Any, account: Any, policy: Any) -> int:
    criteria: dict = {
        "source": "scheduled_incremental",
        "folder_id": policy.folder_id,
        "folder_path": policy.folder_path,
        "only_with_attachments": bool(policy.only_with_attachments),
        "limit": int(policy.limit_per_run or 500),
        "historical_backfill": bool(getattr(policy, "historical_backfill", False)),
    }
    if policy.watermark_at is not None:
        criteria["date_from"] = policy.watermark_at.isoformat()

    if criteria["historical_backfill"]:
        backfill_before = getattr(policy, "backfill_watermark_at", None)
        if backfill_before is None:
            # Bootstrap: oldest already archived, else forward watermark, else skip until first run.
            try:
                from app.infrastructure.persistence.repositories.mail_repos import (
                    SqlAlchemyArchivedMailRepository,
                )

                archived = SqlAlchemyArchivedMailRepository(schedules._db)
                backfill_before = archived.min_received_at(policy.tenant_id, policy.account_id)
            except Exception:
                logger.exception("Could not resolve backfill bootstrap for account=%s", policy.account_id)
                backfill_before = None
            if backfill_before is None:
                backfill_before = policy.watermark_at
        if backfill_before is not None:
            criteria["backfill_before"] = (
                backfill_before.isoformat()
                if hasattr(backfill_before, "isoformat")
                else str(backfill_before)
            )

    job = jobs.create(
        tenant_id=policy.tenant_id,
        user_id=account.user_id,
        account_id=policy.account_id,
        criteria=criteria,
        delete_after_archive=False,
        total_messages=int(policy.limit_per_run or 500),
        total_bytes=0,
        status="pending",
    )
    schedules.mark_enqueued(
        policy.tenant_id,
        policy.account_id,
        job_id=job.id,
        interval_minutes=policy.interval_minutes,
    )
    return int(job.id)


def _enqueue_due(db: Any) -> int:
    from datetime import timedelta

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
            policy.next_run_at = datetime.now(UTC) + timedelta(minutes=max(15, policy.interval_minutes))
            continue
        if jobs.has_open_for_account(policy.tenant_id, policy.account_id):
            policy.next_run_at = datetime.now(UTC) + timedelta(minutes=5)
            policy.last_status = "skipped_busy"
            continue

        job_id = _enqueue_one(schedules, jobs, account, policy)
        created += 1
        logger.info(
            "Scheduled incremental archive enqueued job=%s account=%s tenant=%s",
            job_id,
            policy.account_id,
            policy.tenant_id,
        )
    return created
