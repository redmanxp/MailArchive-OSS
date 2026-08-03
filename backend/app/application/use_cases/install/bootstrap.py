"""Installation use cases."""

from __future__ import annotations

import logging

from app.application.use_cases.users.user_management import generate_temp_password
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import AlreadyInstalledError, ValidationError
from app.domain.interfaces.repositories import (
    IAuditLogRepository,
    IInstallRepository,
    IPasswordHasher,
    ITenantRepository,
    IUserRepository,
)

logger = logging.getLogger(__name__)


class GetInstallationStatusUseCase:
    def __init__(self, install_repo: IInstallRepository) -> None:
        self._install_repo = install_repo

    def execute(self) -> dict:
        installed = self._install_repo.is_installed()
        return {"installed": installed}


class BootstrapInstallationUseCase:
    """Create first tenant + admin user. Returns temporary password once."""

    def __init__(
        self,
        install_repo: IInstallRepository,
        tenant_repo: ITenantRepository,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self._install_repo = install_repo
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_name: str,
        tenant_slug: str,
        admin_name: str,
        admin_email: str,
        admin_password: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        if self._install_repo.is_installed():
            raise AlreadyInstalledError("La aplicación ya está instalada")

        if not tenant_name.strip() or not tenant_slug.strip():
            raise ValidationError("Nombre y slug del tenant son obligatorios")
        if not admin_email.strip() or "@" not in admin_email:
            raise ValidationError("Email de administrador inválido")

        slug = tenant_slug.strip().lower()
        if self._tenant_repo.get_by_slug(slug):
            raise ValidationError(f"Ya existe un tenant con slug '{slug}'")

        temp_password = admin_password or generate_temp_password()
        tenant = self._tenant_repo.create(name=tenant_name.strip(), slug=slug)
        password_hash = self._password_hasher.hash(temp_password)
        admin = self._user_repo.create(
            tenant_id=tenant.id,
            name=admin_name.strip(),
            email=admin_email.strip().lower(),
            password_hash=password_hash,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            must_change_password=True,
        )
        self._install_repo.mark_installed(version="0.1.0-phase0")
        self._audit_repo.add(
            tenant_id=tenant.id,
            user_id=admin.id,
            action="install.bootstrap",
            resource_type="tenant",
            resource_id=str(tenant.id),
            ip=ip,
            user_agent=user_agent,
            details={"admin_email": admin.email, "slug": tenant.slug},
        )
        logger.info(
            "Instalación completada: tenant=%s slug=%s admin=%s",
            tenant.id,
            tenant.slug,
            admin.email,
        )
        return {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "admin_id": admin.id,
            "admin_email": admin.email,
            "temporary_password": temp_password,
            "must_change_password": True,
        }
