"""Authentication use cases."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.domain.enums.roles import UserStatus
from app.domain.exceptions import AuthenticationError, NotInstalledError, ValidationError
from app.domain.interfaces.repositories import (
    IAuditLogRepository,
    IInstallRepository,
    IPasswordHasher,
    IRefreshTokenRepository,
    ITenantRepository,
    ITokenService,
    IUserRepository,
)

logger = logging.getLogger(__name__)


class LoginUseCase:
    def __init__(
        self,
        install_repo: IInstallRepository,
        tenant_repo: ITenantRepository,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        token_service: ITokenService,
        refresh_repo: IRefreshTokenRepository,
        audit_repo: IAuditLogRepository,
        settings: Settings,
    ) -> None:
        self._install_repo = install_repo
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._refresh_repo = refresh_repo
        self._audit_repo = audit_repo
        self._settings = settings

    def execute(
        self,
        *,
        email: str,
        password: str,
        tenant_slug: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        if not self._install_repo.is_installed():
            raise NotInstalledError("La aplicación no está instalada")

        mode = (self._settings.tenant_mode or "single").strip().lower()
        if mode not in ("single", "multi"):
            mode = "single"
        if mode == "single":
            tenants = self._tenant_repo.list_all()
            if len(tenants) == 1:
                tenant = tenants[0]
            elif len(tenants) == 0:
                raise AuthenticationError("Credenciales inválidas")
            else:
                # Misconfigured: single mode but multiple orgs — require explicit slug
                slug = (tenant_slug or "").strip().lower()
                if not slug:
                    raise ValidationError(
                        "Hay varias organizaciones; indicá el tenant o pasá a modo multi en Configuración"
                    )
                tenant = self._tenant_repo.get_by_slug(slug)
                if tenant is None:
                    raise AuthenticationError("Credenciales inválidas")
        else:
            slug = (tenant_slug or self._settings.install_tenant_slug).strip().lower()
            tenant = self._tenant_repo.get_by_slug(slug)
            if tenant is None:
                raise AuthenticationError("Credenciales inválidas")

        user = self._user_repo.get_by_email(tenant.id, email.strip().lower())
        if user is None or not self._password_hasher.verify(password, user.password_hash):
            self._audit_repo.add(
                tenant_id=tenant.id,
                user_id=None,
                action="auth.login_failed",
                details={"email": email.strip().lower()},
                ip=ip,
                user_agent=user_agent,
            )
            raise AuthenticationError("Credenciales inválidas")

        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("Usuario inactivo o bloqueado")

        now = datetime.now(UTC)
        self._user_repo.update_last_login(tenant.id, user.id, now)

        access_claims = {
            "sub": str(user.id),
            "tenant_id": tenant.id,
            "role": user.role.value,
            "email": user.email,
            "must_change_password": user.must_change_password,
        }
        access_token = self._token_service.create_access_token(access_claims)
        refresh_token = self._token_service.create_refresh_token(
            {"sub": str(user.id), "tenant_id": tenant.id, "role": user.role.value}
        )
        expires_at = now + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        self._refresh_repo.store(
            tenant_id=tenant.id,
            user_id=user.id,
            token_hash=self._token_service.hash_token(refresh_token),
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        self._audit_repo.add(
            tenant_id=tenant.id,
            user_id=user.id,
            action="auth.login",
            ip=ip,
            user_agent=user_agent,
        )
        logger.info("Login OK user_id=%s tenant_id=%s", user.id, tenant.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "must_change_password": user.must_change_password,
            "user": {
                "id": user.id,
                "tenant_id": tenant.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "must_change_password": user.must_change_password,
            },
        }


class RefreshTokenUseCase:
    def __init__(
        self,
        token_service: ITokenService,
        refresh_repo: IRefreshTokenRepository,
        user_repo: IUserRepository,
        settings: Settings,
    ) -> None:
        self._token_service = token_service
        self._refresh_repo = refresh_repo
        self._user_repo = user_repo
        self._settings = settings

    def execute(self, refresh_token: str, *, ip: str | None = None, user_agent: str | None = None) -> dict:
        payload = self._token_service.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("Token de refresh inválido")

        token_hash = self._token_service.hash_token(refresh_token)
        valid = self._refresh_repo.get_valid(token_hash)
        if valid is None:
            raise AuthenticationError("Refresh token revocado o expirado")

        tenant_id, user_id = valid
        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("Usuario no válido")

        # Rotación: revocar el actual y emitir nuevo par
        self._refresh_repo.revoke(token_hash)
        access_token = self._token_service.create_access_token(
            {
                "sub": str(user.id),
                "tenant_id": tenant_id,
                "role": user.role.value,
                "email": user.email,
                "must_change_password": user.must_change_password,
            }
        )
        new_refresh = self._token_service.create_refresh_token(
            {"sub": str(user.id), "tenant_id": tenant_id, "role": user.role.value}
        )
        expires_at = datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        self._refresh_repo.store(
            tenant_id=tenant_id,
            user_id=user.id,
            token_hash=self._token_service.hash_token(new_refresh),
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "must_change_password": user.must_change_password,
        }


class LogoutUseCase:
    def __init__(self, token_service: ITokenService, refresh_repo: IRefreshTokenRepository) -> None:
        self._token_service = token_service
        self._refresh_repo = refresh_repo

    def execute(self, refresh_token: str) -> None:
        token_hash = self._token_service.hash_token(refresh_token)
        self._refresh_repo.revoke(token_hash)


class ChangePasswordUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        refresh_repo: IRefreshTokenRepository,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._refresh_repo = refresh_repo
        self._audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        current_password: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        if not new_password.strip():
            raise ValidationError("La nueva contraseña es obligatoria")

        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise AuthenticationError("Usuario no encontrado")
        if not self._password_hasher.verify(current_password, user.password_hash):
            raise AuthenticationError("Contraseña actual incorrecta")
        if current_password == new_password:
            raise ValidationError("La nueva contraseña debe ser distinta a la actual")

        new_hash = self._password_hasher.hash(new_password)
        updated = self._user_repo.update_password(
            tenant_id, user_id, new_hash, must_change_password=False
        )
        self._refresh_repo.revoke_all_for_user(tenant_id, user_id)
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="auth.password_changed",
            ip=ip,
            user_agent=user_agent,
        )
        logger.info("Password changed user_id=%s tenant_id=%s", user_id, tenant_id)
        return {
            "id": updated.id,
            "email": updated.email,
            "must_change_password": updated.must_change_password,
        }
