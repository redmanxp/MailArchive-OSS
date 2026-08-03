"""Domain ports / interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.domain.entities.user import AuditLog, Tenant, User
from app.domain.enums.roles import UserRole, UserStatus


class IPasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool: ...


class ITokenService(ABC):
    @abstractmethod
    def create_access_token(self, claims: dict[str, Any]) -> str: ...

    @abstractmethod
    def create_refresh_token(self, claims: dict[str, Any]) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> dict[str, Any]: ...

    @abstractmethod
    def hash_token(self, token: str) -> str: ...


class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, tenant_id: int, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_email(self, tenant_id: int, email: str) -> User | None: ...

    @abstractmethod
    def create(
        self,
        *,
        tenant_id: int,
        name: str,
        email: str,
        password_hash: str,
        role: UserRole,
        status: UserStatus,
        must_change_password: bool,
    ) -> User: ...

    @abstractmethod
    def update_password(
        self,
        tenant_id: int,
        user_id: int,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> User: ...

    @abstractmethod
    def update_last_login(self, tenant_id: int, user_id: int, when: datetime) -> None: ...

    @abstractmethod
    def list_by_tenant(self, tenant_id: int) -> list[User]: ...

    @abstractmethod
    def update_profile(
        self,
        tenant_id: int,
        user_id: int,
        *,
        name: str | None = None,
        role: UserRole | None = None,
        status: UserStatus | None = None,
    ) -> User | None: ...

    @abstractmethod
    def deactivate(self, tenant_id: int, user_id: int) -> bool: ...


class ITenantRepository(ABC):
    @abstractmethod
    def get_by_id(self, tenant_id: int) -> Tenant | None: ...

    @abstractmethod
    def get_by_slug(self, slug: str) -> Tenant | None: ...

    @abstractmethod
    def create(self, *, name: str, slug: str) -> Tenant: ...


class IInstallRepository(ABC):
    @abstractmethod
    def is_installed(self) -> bool: ...

    @abstractmethod
    def mark_installed(self, version: str) -> None: ...


class IRefreshTokenRepository(ABC):
    @abstractmethod
    def store(
        self,
        *,
        tenant_id: int,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip: str | None,
    ) -> None: ...

    @abstractmethod
    def get_valid(self, token_hash: str) -> tuple[int, int] | None:
        """Return (tenant_id, user_id) if valid."""

    @abstractmethod
    def revoke(self, token_hash: str) -> None: ...

    @abstractmethod
    def revoke_all_for_user(self, tenant_id: int, user_id: int) -> None: ...


class IAuditLogRepository(ABC):
    @abstractmethod
    def add(
        self,
        *,
        tenant_id: int | None,
        user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
    ) -> AuditLog: ...
