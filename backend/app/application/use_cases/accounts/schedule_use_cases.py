"""Archive schedule use cases (incremental archive policies — not sync)."""

from __future__ import annotations

import logging

from app.domain.enums.providers import AccountStatus
from app.domain.enums.roles import UserRole
from app.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.interfaces.repositories import IAuditLogRepository
from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyMailAccountRepository
from app.infrastructure.persistence.repositories.schedule_repo import SqlAlchemyArchiveScheduleRepository

logger = logging.getLogger(__name__)


class GetArchiveScheduleUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        schedule_repo: SqlAlchemyArchiveScheduleRepository,
    ) -> None:
        self.account_repo = account_repo
        self.schedule_repo = schedule_repo

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, account_id: int) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede ver la programación de esta cuenta")
        row = self.schedule_repo.get_or_create(tenant_id, account_id)
        return self.schedule_repo.to_public(row)


class UpdateArchiveScheduleUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        schedule_repo: SqlAlchemyArchiveScheduleRepository,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.account_repo = account_repo
        self.schedule_repo = schedule_repo
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        enabled: bool,
        interval_minutes: int,
        folder_id: str | None = None,
        folder_path: str | None = None,
        limit_per_run: int = 500,
        only_with_attachments: bool = False,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede programar esta cuenta")
        if enabled and (
            account.status == AccountStatus.UNLINKED.value or not account.credentials_encrypted
        ):
            raise ValidationError("No se puede activar el archivo programado en una cuenta desvinculada")
        if interval_minutes < 15:
            raise ValidationError("El intervalo mínimo es 15 minutos")
        row = self.schedule_repo.upsert(
            tenant_id=tenant_id,
            account_id=account_id,
            enabled=enabled,
            interval_minutes=interval_minutes,
            folder_id=folder_id,
            folder_path=folder_path,
            limit_per_run=limit_per_run,
            only_with_attachments=only_with_attachments,
        )
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="archive_schedule.updated",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={
                "enabled": enabled,
                "interval_minutes": interval_minutes,
                "folder_id": folder_id,
                "limit_per_run": limit_per_run,
            },
        )
        logger.info(
            "Archive schedule account=%s enabled=%s interval=%sm",
            account_id,
            enabled,
            interval_minutes,
        )
        return self.schedule_repo.to_public(row)
