"""Dashboard metrics endpoint."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user
from app.config import Settings, get_settings
from app.domain.enums.roles import UserRole
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import (
    ArchiveJobModel,
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

    health: DashboardHealth | None = None
    if role == UserRole.ADMIN:
        db_ok = False
        try:
            db_ok = db.execute(text("SELECT 1")).scalar() == 1
        except Exception as exc:
            logger.warning("dashboard db health failed: %s", exc)
        storage_path = Path(settings.storage_root)
        storage_ok = False
        try:
            storage_path.mkdir(parents=True, exist_ok=True)
            storage_ok = storage_path.is_dir()
        except Exception as exc:
            logger.warning("dashboard storage health failed: %s", exc)
        health = DashboardHealth(
            db_ok=db_ok,
            storage_ok=storage_ok,
            storage_root=str(storage_path),
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
        health=health,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
