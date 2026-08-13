"""Repository for per-account archive schedules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import ArchiveScheduleModel


def _aware_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; job watermarks are UTC-aware. Compare safely."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class SqlAlchemyArchiveScheduleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_account(self, tenant_id: int, account_id: int) -> ArchiveScheduleModel | None:
        return self._db.scalar(
            select(ArchiveScheduleModel).where(
                ArchiveScheduleModel.tenant_id == tenant_id,
                ArchiveScheduleModel.account_id == account_id,
            )
        )

    def get_or_create(self, tenant_id: int, account_id: int) -> ArchiveScheduleModel:
        row = self.get_by_account(tenant_id, account_id)
        if row:
            return row
        row = ArchiveScheduleModel(
            tenant_id=tenant_id,
            account_id=account_id,
            enabled=False,
            interval_minutes=1440,
            limit_per_run=500,
            only_with_attachments=False,
            historical_backfill=False,
        )
        self._db.add(row)
        self._db.flush()
        return row

    def upsert(
        self,
        *,
        tenant_id: int,
        account_id: int,
        enabled: bool,
        interval_minutes: int,
        folder_id: str | None,
        folder_path: str | None,
        limit_per_run: int,
        only_with_attachments: bool,
        historical_backfill: bool = False,
    ) -> ArchiveScheduleModel:
        row = self.get_or_create(tenant_id, account_id)
        was_enabled = bool(row.enabled)
        row.enabled = bool(enabled)
        row.interval_minutes = max(15, min(int(interval_minutes), 60 * 24 * 30))
        row.folder_id = folder_id or None
        row.folder_path = folder_path or None
        row.limit_per_run = max(1, min(int(limit_per_run), 2000))
        row.only_with_attachments = bool(only_with_attachments)
        row.historical_backfill = bool(historical_backfill)
        if not row.historical_backfill:
            row.backfill_watermark_at = None
        now = datetime.now(UTC)
        if row.enabled:
            if not was_enabled or row.next_run_at is None:
                # First enable: run soon (within a minute) then follow interval.
                row.next_run_at = now
            # If already enabled, keep next_run_at unless it was cleared
        else:
            row.next_run_at = None
            row.last_status = row.last_status or "disabled"
        self._db.flush()
        return row

    def list_due(self, *, now: datetime | None = None, limit: int = 20) -> list[ArchiveScheduleModel]:
        ts = now or datetime.now(UTC)
        stmt = (
            select(ArchiveScheduleModel)
            .where(
                ArchiveScheduleModel.enabled.is_(True),
                ArchiveScheduleModel.next_run_at.is_not(None),
                ArchiveScheduleModel.next_run_at <= ts,
            )
            .order_by(ArchiveScheduleModel.next_run_at.asc())
            .limit(limit)
        )
        return list(self._db.scalars(stmt).all())

    def mark_enqueued(
        self,
        tenant_id: int,
        account_id: int,
        *,
        job_id: int,
        interval_minutes: int,
    ) -> None:
        row = self.get_by_account(tenant_id, account_id)
        if not row:
            return
        now = datetime.now(UTC)
        row.last_run_at = now
        row.last_job_id = job_id
        row.last_status = "queued"
        row.last_error = None
        row.next_run_at = now + timedelta(minutes=max(15, interval_minutes))
        self._db.flush()

    def mark_job_finished(
        self,
        tenant_id: int,
        account_id: int,
        *,
        job_id: int,
        status: str,
        error: str | None = None,
        watermark_at: datetime | None = None,
        backfill_watermark_at: datetime | None = None,
    ) -> None:
        row = self.get_by_account(tenant_id, account_id)
        if not row:
            return
        if row.last_job_id is not None and row.last_job_id != job_id:
            # Older job finished after a newer one was queued — still record status lightly
            pass
        row.last_status = status
        row.last_error = (error or None) and str(error)[:1000]
        wm_new = _aware_utc(watermark_at)
        wm_old = _aware_utc(row.watermark_at)
        if wm_new is not None:
            if wm_old is None or wm_new > wm_old:
                row.watermark_at = wm_new
        bf_new = _aware_utc(backfill_watermark_at)
        bf_old = _aware_utc(row.backfill_watermark_at)
        if bf_new is not None and row.historical_backfill:
            if bf_old is None or bf_new < bf_old:
                row.backfill_watermark_at = bf_new
        self._db.flush()

    def to_public(self, row: ArchiveScheduleModel) -> dict[str, Any]:
        return {
            "account_id": row.account_id,
            "enabled": bool(row.enabled),
            "interval_minutes": row.interval_minutes,
            "folder_id": row.folder_id,
            "folder_path": row.folder_path,
            "limit_per_run": row.limit_per_run,
            "only_with_attachments": bool(row.only_with_attachments),
            "historical_backfill": bool(row.historical_backfill),
            "watermark_at": row.watermark_at.isoformat() if row.watermark_at else None,
            "backfill_watermark_at": (
                row.backfill_watermark_at.isoformat() if row.backfill_watermark_at else None
            ),
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
            "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
            "last_job_id": row.last_job_id,
            "last_status": row.last_status,
            "last_error": row.last_error,
        }

    def delete_for_account(self, tenant_id: int, account_id: int) -> bool:
        result = self._db.execute(
            delete(ArchiveScheduleModel).where(
                ArchiveScheduleModel.tenant_id == tenant_id,
                ArchiveScheduleModel.account_id == account_id,
            )
        )
        self._db.flush()
        return bool(result.rowcount)

    def list_enabled_account_ids(self, tenant_id: int) -> set[int]:
        rows = self._db.scalars(
            select(ArchiveScheduleModel.account_id).where(
                ArchiveScheduleModel.tenant_id == tenant_id,
                ArchiveScheduleModel.enabled.is_(True),
            )
        ).all()
        return set(int(x) for x in rows)

    def force_due_now(self, tenant_id: int, account_id: int) -> ArchiveScheduleModel | None:
        """Set next_run_at to now so the dispatcher picks it up immediately."""
        row = self.get_by_account(tenant_id, account_id)
        if row is None or not row.enabled:
            return None
        row.next_run_at = datetime.now(UTC)
        self._db.flush()
        return row
