"""Archive job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import ArchiveJobModel


class SqlAlchemyArchiveJobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        account_id: int,
        criteria: dict[str, Any],
        delete_after_archive: bool,
        total_messages: int,
        total_bytes: int,
        status: str = "pending",
    ) -> ArchiveJobModel:
        row = ArchiveJobModel(
            tenant_id=tenant_id,
            user_id=user_id,
            account_id=account_id,
            status=status,
            criteria=criteria,
            delete_after_archive=delete_after_archive,
            total_messages=total_messages,
            total_bytes=total_bytes,
        )
        self._db.add(row)
        self._db.flush()
        return row

    def get(self, tenant_id: int, job_id: int) -> ArchiveJobModel | None:
        return self._db.scalar(
            select(ArchiveJobModel).where(
                ArchiveJobModel.tenant_id == tenant_id, ArchiveJobModel.id == job_id
            )
        )

    def list_pending(self, *, limit: int = 5) -> list[ArchiveJobModel]:
        """Oldest pending jobs across tenants (single-node dispatcher)."""
        stmt = (
            select(ArchiveJobModel)
            .where(ArchiveJobModel.status == "pending")
            .order_by(ArchiveJobModel.id.asc())
            .limit(limit)
        )
        return list(self._db.scalars(stmt).all())

    def has_open_for_account(self, tenant_id: int, account_id: int) -> bool:
        row = self._db.scalar(
            select(ArchiveJobModel.id).where(
                ArchiveJobModel.tenant_id == tenant_id,
                ArchiveJobModel.account_id == account_id,
                ArchiveJobModel.status.in_(("pending", "running")),
            )
        )
        return row is not None

    def try_claim(self, tenant_id: int, job_id: int) -> ArchiveJobModel | None:
        """Atomically move pending → running. Returns None if already claimed."""
        from sqlalchemy import update

        now = datetime.now(UTC)
        result = self._db.execute(
            update(ArchiveJobModel)
            .where(
                ArchiveJobModel.tenant_id == tenant_id,
                ArchiveJobModel.id == job_id,
                ArchiveJobModel.status == "pending",
            )
            .values(status="running", started_at=now, updated_at=now)
        )
        self._db.flush()
        if not result.rowcount:
            return None
        return self.get(tenant_id, job_id)

    def list_for_tenant(self, tenant_id: int, *, user_id: int | None = None, limit: int = 50) -> list[ArchiveJobModel]:
        stmt = select(ArchiveJobModel).where(ArchiveJobModel.tenant_id == tenant_id)
        if user_id is not None:
            stmt = stmt.where(ArchiveJobModel.user_id == user_id)
        stmt = stmt.order_by(ArchiveJobModel.id.desc()).limit(limit)
        return list(self._db.scalars(stmt).all())

    def update_progress(
        self,
        tenant_id: int,
        job_id: int,
        *,
        status: str | None = None,
        processed: int | None = None,
        archived: int | None = None,
        skipped: int | None = None,
        failed: int | None = None,
        archived_bytes: int | None = None,
        error_message: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> ArchiveJobModel | None:
        row = self.get(tenant_id, job_id)
        if row is None:
            return None
        if status is not None:
            row.status = status
        if processed is not None:
            row.processed_messages = processed
        if archived is not None:
            row.archived_messages = archived
        if skipped is not None:
            row.skipped_messages = skipped
        if failed is not None:
            row.failed_messages = failed
        if archived_bytes is not None:
            row.archived_bytes = archived_bytes
        if error_message is not None:
            row.error_message = error_message
        if started and row.started_at is None:
            row.started_at = datetime.now(UTC)
        if finished:
            row.finished_at = datetime.now(UTC)
        self._db.flush()
        return row

    def fail_open_for_account(self, tenant_id: int, account_id: int, message: str) -> int:
        """Mark pending/running jobs for an account as failed. Returns count."""
        rows = list(
            self._db.scalars(
                select(ArchiveJobModel).where(
                    ArchiveJobModel.tenant_id == tenant_id,
                    ArchiveJobModel.account_id == account_id,
                    ArchiveJobModel.status.in_(("pending", "running")),
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.status = "failed"
            row.error_message = message
            row.finished_at = now
        if rows:
            self._db.flush()
        return len(rows)

    def reset_for_retry(self, tenant_id: int, job_id: int) -> ArchiveJobModel | None:
        """Reset failed/cancelled job counters and set status=pending."""
        row = self.get(tenant_id, job_id)
        if row is None:
            return None
        if row.status not in ("failed", "cancelled"):
            return None
        row.status = "pending"
        row.processed_messages = 0
        row.archived_messages = 0
        row.skipped_messages = 0
        row.failed_messages = 0
        row.archived_bytes = 0
        row.error_message = None
        row.started_at = None
        row.finished_at = None
        if isinstance(row.criteria, dict) and "__result" in row.criteria:
            cleaned = dict(row.criteria)
            cleaned.pop("__result", None)
            row.criteria = cleaned
        self._db.flush()
        return row

    def set_result(self, tenant_id: int, job_id: int, result: dict[str, Any]) -> None:
        """Attach a compact result summary under criteria['__result'] (no schema migration)."""
        row = self.get(tenant_id, job_id)
        if row is None:
            return
        base = dict(row.criteria or {})
        base["__result"] = result
        row.criteria = base
        self._db.flush()

    def reassign_user_for_account(self, tenant_id: int, account_id: int, new_user_id: int) -> int:
        rows = list(
            self._db.scalars(
                select(ArchiveJobModel).where(
                    ArchiveJobModel.tenant_id == tenant_id,
                    ArchiveJobModel.account_id == account_id,
                )
            ).all()
        )
        for row in rows:
            row.user_id = new_user_id
        if rows:
            self._db.flush()
        return len(rows)

    def delete_for_account(self, tenant_id: int, account_id: int) -> int:
        result = self._db.execute(
            delete(ArchiveJobModel).where(
                ArchiveJobModel.tenant_id == tenant_id,
                ArchiveJobModel.account_id == account_id,
            )
        )
        self._db.flush()
        return int(result.rowcount or 0)
