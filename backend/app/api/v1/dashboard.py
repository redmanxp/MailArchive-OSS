"""Dashboard metrics endpoint."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user
from app.config import Settings, get_settings
from app.domain.enums.roles import UserRole
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import (
    ArchiveJobModel,
    ArchiveScheduleModel,
    ArchivedMailModel,
    AttachmentModel,
    MailAccountModel,
    UserModel,
)
from app.schemas.dashboard import DashboardHealth, DashboardMetricsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DashboardMetricsResponse:
    """Tenant-scoped metrics for the dashboard. Admin/supervisor see tenant totals."""
    tenant_id = ctx.user.tenant_id
    role = ctx.user.role
    is_staff = role in (UserRole.ADMIN, UserRole.SUPERVISOR)
    scope = "tenant" if is_staff else "own"
    scope_user_id = None if is_staff else ctx.user.id

    users_count: int | None = None
    if role == UserRole.ADMIN:
        users_count = int(
            db.scalar(
                select(func.count())
                .select_from(UserModel)
                .where(UserModel.tenant_id == tenant_id, UserModel.deleted_at.is_(None))
            )
            or 0
        )

    acc_q = select(func.count()).select_from(MailAccountModel).where(MailAccountModel.tenant_id == tenant_id)
    mail_q = select(func.count()).select_from(ArchivedMailModel).where(ArchivedMailModel.tenant_id == tenant_id)
    size_q = select(func.coalesce(func.sum(ArchivedMailModel.size_bytes), 0)).where(
        ArchivedMailModel.tenant_id == tenant_id
    )
    if scope_user_id is not None:
        acc_q = acc_q.where(MailAccountModel.user_id == scope_user_id)
        mail_q = mail_q.where(ArchivedMailModel.user_id == scope_user_id)
        size_q = size_q.where(ArchivedMailModel.user_id == scope_user_id)

    accounts_count = int(db.scalar(acc_q) or 0)
    mails_count = int(db.scalar(mail_q) or 0)
    storage_bytes = int(db.scalar(size_q) or 0)

    if scope_user_id is None:
        att_q = (
            select(func.count())
            .select_from(AttachmentModel)
            .where(AttachmentModel.tenant_id == tenant_id)
        )
    else:
        att_q = (
            select(func.count())
            .select_from(AttachmentModel)
            .join(ArchivedMailModel, ArchivedMailModel.id == AttachmentModel.archived_mail_id)
            .where(
                AttachmentModel.tenant_id == tenant_id,
                ArchivedMailModel.user_id == scope_user_id,
            )
        )
    attachments_count = int(db.scalar(att_q) or 0)

    jq = select(func.count()).select_from(ArchiveJobModel).where(
        ArchiveJobModel.tenant_id == tenant_id,
        ArchiveJobModel.status.in_(("pending", "running", "cancelling")),
    )
    if scope_user_id is not None:
        jq = jq.where(ArchiveJobModel.user_id == scope_user_id)
    jobs_active = int(db.scalar(jq) or 0)

    jf = select(func.count()).select_from(ArchiveJobModel).where(
        ArchiveJobModel.tenant_id == tenant_id,
        ArchiveJobModel.status == "failed",
    )
    if scope_user_id is not None:
        jf = jf.where(ArchiveJobModel.user_id == scope_user_id)
    jobs_failed = int(db.scalar(jf) or 0)

    sched_q = (
        select(func.count())
        .select_from(ArchiveScheduleModel)
        .join(MailAccountModel, MailAccountModel.id == ArchiveScheduleModel.account_id)
        .where(
            ArchiveScheduleModel.tenant_id == tenant_id,
            MailAccountModel.tenant_id == tenant_id,
            ArchiveScheduleModel.enabled.is_(True),
            or_(
                ArchiveScheduleModel.last_status == "failed",
                (
                    ArchiveScheduleModel.last_error.is_not(None)
                    & (ArchiveScheduleModel.last_error != "")
                ),
            ),
        )
    )
    if scope_user_id is not None:
        sched_q = sched_q.where(MailAccountModel.user_id == scope_user_id)
    schedules_with_errors = int(db.scalar(sched_q) or 0)

    last_q = select(func.max(ArchiveJobModel.finished_at)).where(
        ArchiveJobModel.tenant_id == tenant_id,
        ArchiveJobModel.status.in_(("completed", "failed", "cancelled")),
        ArchiveJobModel.finished_at.is_not(None),
    )
    if scope_user_id is not None:
        last_q = last_q.where(ArchiveJobModel.user_id == scope_user_id)
    last_finished = db.scalar(last_q)
    last_archive_at = last_finished.isoformat() if last_finished is not None else None

    health: DashboardHealth | None = None
    if role == UserRole.ADMIN:
        db_ok = False
        try:
            db_ok = db.execute(text("SELECT 1")).scalar() == 1
        except Exception as exc:
            logger.warning("dashboard db health failed: %s", exc)
        storage_ok = False
        storage_label = settings.storage_root
        try:
            from app.infrastructure.storage.factory import build_mail_storage

            ok, detail = build_mail_storage(settings).health_check()
            storage_ok = ok
            storage_label = detail
        except Exception as exc:
            logger.warning("dashboard storage health failed: %s", exc)
            storage_label = str(exc)
        health = DashboardHealth(
            db_ok=db_ok,
            storage_ok=storage_ok,
            storage_root=storage_label,
        )

    return DashboardMetricsResponse(
        tenant_id=tenant_id,
        scope=scope,
        users_count=users_count,
        accounts_count=accounts_count,
        mails_count=mails_count,
        storage_bytes=storage_bytes,
        attachments_count=attachments_count,
        jobs_active=jobs_active,
        jobs_failed=jobs_failed,
        schedules_with_errors=schedules_with_errors,
        last_archive_at=last_archive_at,
        health=health,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
