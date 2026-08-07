"""Employee departure — guided offboarding orchestrating archive + deactivate."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.domain.enums.providers import AccountStatus
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.interfaces.repositories import IAuditLogRepository, IUserRepository
from app.application.use_cases.accounts.bulk_archive import StartBulkArchiveUseCase
from app.application.use_cases.users.user_management import DeactivateUserUseCase
from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.schedule_repo import SqlAlchemyArchiveScheduleRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.security.fernet_cipher import CredentialCipher

logger = logging.getLogger(__name__)


class EmployeeDepartureUseCase:
    """Archive (optional) → disable schedules → unlink/transfer accounts → deactivate user.

    Jobs run asynchronously; deactivation does not wait for them to finish.
    When archive is enabled, accounts_action must be ``transfer`` so credentials
    remain available for the running jobs (soft-unlink clears tokens).
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        account_repo: SqlAlchemyMailAccountRepository,
        audit_repo: IAuditLogRepository,
        settings: Settings,
        cipher: CredentialCipher,
        job_repo: SqlAlchemyArchiveJobRepository,
        archived_repo: SqlAlchemyArchivedMailRepository | None = None,
        schedule_repo: SqlAlchemyArchiveScheduleRepository | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._account_repo = account_repo
        self._audit_repo = audit_repo
        self._settings = settings
        self._cipher = cipher
        self._job_repo = job_repo
        self._archived_repo = archived_repo
        self._schedule_repo = schedule_repo
        self._factory = MailProviderFactory(settings, cipher)

    def preview(self, *, tenant_id: int, user_id: int) -> dict:
        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        accounts = [
            a
            for a in self._account_repo.list_for_user(tenant_id, user_id)
            if a.status != AccountStatus.UNLINKED.value
        ]
        return {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "status": user.status.value if hasattr(user.status, "value") else str(user.status),
                "must_change_password": bool(getattr(user, "must_change_password", False)),
            },
            "accounts": [
                {
                    "id": a.id,
                    "email": a.email,
                    "provider": a.provider,
                    "status": a.status,
                }
                for a in accounts
            ],
        }

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        actor_role: UserRole,
        user_id: int,
        accounts_action: str = "unlink",
        transfer_to_user_id: int | None = None,
        archive_enabled: bool = False,
        older_than_days: int | None = None,
        archive_limit: int = 500,
        disable_schedules: bool = True,
    ) -> dict:
        if actor_role != UserRole.ADMIN:
            raise AuthorizationError("Solo un administrador puede ejecutar la baja de empleado")
        if actor_user_id == user_id:
            raise ValidationError("No podés dar de baja tu propio usuario")

        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        status_val = getattr(user.status, "value", user.status)
        if status_val != UserStatus.ACTIVE.value:
            raise ValidationError("El usuario ya no está activo")

        action = (accounts_action or "unlink").strip().lower()
        if action not in ("unlink", "transfer"):
            raise ValidationError("accounts_action must be unlink or transfer")

        accounts = [
            a
            for a in self._account_repo.list_for_user(tenant_id, user_id)
            if a.status != AccountStatus.UNLINKED.value
        ]

        # Soft-unlink clears credentials; archive jobs need them. Force transfer.
        if archive_enabled and accounts and action == "unlink":
            raise ValidationError(
                "Si archivás el buzón, transferí las cuentas a un administrador "
                "(los jobs necesitan las credenciales). Después podés desvincular."
            )
        if archive_enabled and accounts and action == "transfer" and not transfer_to_user_id:
            raise ValidationError("transfer_to_user_id es obligatorio al archivar")

        job_ids: list[int] = []
        archive_skipped: list[dict[str, Any]] = []
        if archive_enabled and accounts:
            starter = StartBulkArchiveUseCase(
                self._account_repo,
                self._job_repo,
                self._factory,
                self._cipher,
                self._audit_repo,
                self._settings,
            )
            criteria: dict[str, Any] = {}
            if older_than_days is not None and older_than_days >= 1:
                criteria["older_than_days"] = older_than_days
            for acc in accounts:
                if not acc.credentials_encrypted:
                    archive_skipped.append(
                        {"account_id": acc.id, "email": acc.email, "reason": "sin_credenciales"}
                    )
                    continue
                try:
                    result = starter.execute(
                        tenant_id=tenant_id,
                        user_id=actor_user_id,
                        role=actor_role,
                        account_id=acc.id,
                        criteria=criteria,
                        delete_after_archive=False,
                        limit=max(1, min(int(archive_limit), 2000)),
                    )
                    job_ids.append(int(result["id"]))
                except ValidationError as exc:
                    archive_skipped.append(
                        {"account_id": acc.id, "email": acc.email, "reason": str(exc)}
                    )
                    logger.info(
                        "Departure archive skipped account_id=%s: %s",
                        acc.id,
                        exc,
                    )

        schedules_disabled = 0
        if disable_schedules and self._schedule_repo is not None:
            for acc in accounts:
                row = self._schedule_repo.get_by_account(tenant_id, acc.id)
                if row is not None and row.enabled:
                    self._schedule_repo.upsert(
                        tenant_id=tenant_id,
                        account_id=acc.id,
                        enabled=False,
                        interval_minutes=row.interval_minutes,
                        folder_id=row.folder_id,
                        folder_path=row.folder_path,
                        limit_per_run=row.limit_per_run,
                        only_with_attachments=bool(row.only_with_attachments),
                        historical_backfill=bool(getattr(row, "historical_backfill", False)),
                    )
                    schedules_disabled += 1

        deactivate = DeactivateUserUseCase(
            self._user_repo,
            self._audit_repo,
            account_repo=self._account_repo,
            archived_repo=self._archived_repo,
            job_repo=self._job_repo,
        )
        deact = deactivate.execute(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            user_id=user_id,
            accounts_action=action,
            transfer_to_user_id=transfer_to_user_id,
        )

        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.departure",
            resource_type="user",
            resource_id=str(user_id),
            details={
                "email": user.email,
                "accounts_action": deact.get("accounts_action"),
                "accounts_touched": deact.get("accounts_touched"),
                "transfer_to_user_id": transfer_to_user_id,
                "job_ids": job_ids,
                "archive_skipped": archive_skipped,
                "schedules_disabled": schedules_disabled,
                "archive_enabled": archive_enabled,
            },
        )
        logger.info(
            "Employee departure user_id=%s email=%s jobs=%s accounts=%s",
            user_id,
            user.email,
            job_ids,
            deact.get("accounts_touched"),
        )
        return {
            "user_id": user_id,
            "email": user.email,
            "deactivated": True,
            "accounts_action": deact.get("accounts_action"),
            "accounts_touched": deact.get("accounts_touched", 0),
            "mails_reassigned": deact.get("mails_reassigned", 0),
            "job_ids": job_ids,
            "archive_skipped": archive_skipped,
            "schedules_disabled": schedules_disabled,
        }
