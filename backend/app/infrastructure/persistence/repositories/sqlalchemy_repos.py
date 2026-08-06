"""SQLAlchemy repository implementations — Phase 0."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.domain.entities.user import AuditLog, Tenant, User
from app.domain.enums.roles import TenantStatus, UserRole, UserStatus
from app.domain.interfaces.repositories import (
    IAuditLogRepository,
    IInstallRepository,
    IRefreshTokenRepository,
    ITenantRepository,
    IUserRepository,
)
from app.infrastructure.persistence.models import (
    AuditLogModel,
    InstallStateModel,
    RefreshTokenModel,
    TenantModel,
    TenantSettingsModel,
    UserModel,
)

logger = logging.getLogger(__name__)


def _to_user(row: UserModel) -> User:
    return User(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        email=row.email,
        password_hash=row.password_hash,
        role=UserRole(row.role),
        status=UserStatus(row.status),
        must_change_password=row.must_change_password,
        last_login_at=row.last_login_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _to_tenant(row: TenantModel) -> Tenant:
    return Tenant(
        id=row.id,
        name=row.name,
        slug=row.slug,
        status=TenantStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyInstallRepository(IInstallRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def is_installed(self) -> bool:
        row = self._db.get(InstallStateModel, 1)
        return bool(row and row.installed)

    def mark_installed(self, version: str) -> None:
        row = self._db.get(InstallStateModel, 1)
        now = datetime.now(UTC)
        if row is None:
            row = InstallStateModel(id=1, installed=True, installed_at=now, version=version)
            self._db.add(row)
        else:
            row.installed = True
            row.installed_at = now
            row.version = version
        self._db.flush()


class SqlAlchemyTenantRepository(ITenantRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, tenant_id: int) -> Tenant | None:
        row = self._db.get(TenantModel, tenant_id)
        return _to_tenant(row) if row else None

    def get_by_slug(self, slug: str) -> Tenant | None:
        row = self._db.scalar(select(TenantModel).where(TenantModel.slug == slug))
        return _to_tenant(row) if row else None

    def create(self, *, name: str, slug: str) -> Tenant:
        row = TenantModel(name=name, slug=slug, status=TenantStatus.ACTIVE.value)
        self._db.add(row)
        self._db.flush()
        settings = TenantSettingsModel(tenant_id=row.id, features={"phase": 0})
        self._db.add(settings)
        self._db.flush()
        return _to_tenant(row)

    def list_all(self) -> list[Tenant]:
        rows = self._db.scalars(select(TenantModel).order_by(TenantModel.id.asc())).all()
        return [_to_tenant(r) for r in rows]


class SqlAlchemyUserRepository(IUserRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, tenant_id: int, user_id: int) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )
        return _to_user(row) if row else None

    def get_by_email(self, tenant_id: int, email: str) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.email == email.lower(),
                UserModel.deleted_at.is_(None),
            )
        )
        return _to_user(row) if row else None

    def get_deleted_by_email(self, tenant_id: int, email: str) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.email == email.lower(),
                UserModel.deleted_at.is_not(None),
            )
        )
        return _to_user(row) if row else None

    def restore(
        self,
        tenant_id: int,
        user_id: int,
        *,
        name: str,
        password_hash: str,
        role: UserRole,
        status: UserStatus,
        must_change_password: bool,
    ) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_not(None),
            )
        )
        if row is None:
            return None
        row.deleted_at = None
        row.name = name
        row.password_hash = password_hash
        row.role = role.value
        row.status = status.value
        row.must_change_password = must_change_password
        self._db.flush()
        logger.info("Restored soft-deleted user_id=%s tenant_id=%s email=%s", user_id, tenant_id, row.email)
        return _to_user(row)

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
    ) -> User:
        row = UserModel(
            tenant_id=tenant_id,
            name=name,
            email=email.lower(),
            password_hash=password_hash,
            role=role.value,
            status=status.value,
            must_change_password=must_change_password,
        )
        self._db.add(row)
        self._db.flush()
        return _to_user(row)

    def update_password(
        self,
        tenant_id: int,
        user_id: int,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> User:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )
        if row is None:
            raise ValueError("Usuario no encontrado")
        row.password_hash = password_hash
        row.must_change_password = must_change_password
        self._db.flush()
        return _to_user(row)

    def update_last_login(self, tenant_id: int, user_id: int, when: datetime) -> None:
        self._db.execute(
            update(UserModel)
            .where(UserModel.tenant_id == tenant_id, UserModel.id == user_id)
            .values(last_login_at=when)
        )
        self._db.flush()

    def list_by_tenant(self, tenant_id: int, *, only_deleted: bool = False) -> list[User]:
        q = select(UserModel).where(UserModel.tenant_id == tenant_id)
        if only_deleted:
            q = q.where(UserModel.deleted_at.is_not(None))
        else:
            q = q.where(UserModel.deleted_at.is_(None))
        rows = self._db.scalars(q.order_by(UserModel.id)).all()
        return [_to_user(r) for r in rows]

    def get_by_id_any(self, tenant_id: int, user_id: int) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(UserModel.tenant_id == tenant_id, UserModel.id == user_id)
        )
        return _to_user(row) if row else None

    def hard_delete(self, tenant_id: int, user_id: int) -> bool:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_not(None),
            )
        )
        if row is None:
            return False
        self._db.delete(row)
        self._db.flush()
        logger.info("Hard-deleted user_id=%s tenant_id=%s email=%s", user_id, tenant_id, row.email)
        return True

    def update_profile(
        self,
        tenant_id: int,
        user_id: int,
        *,
        name: str | None = None,
        role: UserRole | None = None,
        status: UserStatus | None = None,
    ) -> User | None:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )
        if row is None:
            return None
        if name is not None:
            row.name = name.strip()
        if role is not None:
            row.role = role.value
        if status is not None:
            row.status = status.value
        self._db.flush()
        return _to_user(row)

    def deactivate(self, tenant_id: int, user_id: int) -> bool:
        row = self._db.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )
        if row is None:
            return False
        row.status = UserStatus.INACTIVE.value
        row.deleted_at = datetime.now(UTC)
        self._db.flush()
        return True


class SqlAlchemyRefreshTokenRepository(IRefreshTokenRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def store(
        self,
        *,
        tenant_id: int,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip: str | None,
    ) -> None:
        self._db.add(
            RefreshTokenModel(
                tenant_id=tenant_id,
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
                ip=ip,
            )
        )
        self._db.flush()

    def get_valid(self, token_hash: str) -> tuple[int, int] | None:
        row = self._db.scalar(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked_at.is_(None),
            )
        )
        if row is None:
            return None
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            return None
        return row.tenant_id, row.user_id

    def revoke(self, token_hash: str) -> None:
        row = self._db.scalar(select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash))
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            self._db.flush()

    def revoke_all_for_user(self, tenant_id: int, user_id: int) -> None:
        rows = self._db.scalars(
            select(RefreshTokenModel).where(
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
        ).all()
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
        self._db.flush()

    def delete_all_for_user(self, tenant_id: int, user_id: int) -> int:
        """Remove refresh token rows so the user FK can be hard-deleted."""
        result = self._db.execute(
            delete(RefreshTokenModel).where(
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.user_id == user_id,
            )
        )
        self._db.flush()
        return int(result.rowcount or 0)


class SqlAlchemyAuditLogRepository(IAuditLogRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

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
    ) -> AuditLog:
        row = AuditLogModel(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip,
            user_agent=user_agent,
            details=details,
        )
        self._db.add(row)
        self._db.flush()
        return AuditLog(
            id=row.id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            ip=row.ip,
            user_agent=row.user_agent,
            details=row.details,
            created_at=row.created_at,
        )

    def nullify_user(self, tenant_id: int, user_id: int) -> int:
        """Detach audit rows from a user before hard-delete (keep history)."""
        result = self._db.execute(
            update(AuditLogModel)
            .where(AuditLogModel.tenant_id == tenant_id, AuditLogModel.user_id == user_id)
            .values(user_id=None)
        )
        self._db.flush()
        return int(result.rowcount or 0)

    def search(
        self,
        tenant_id: int,
        *,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLogModel], int]:
        from sqlalchemy import cast, func, or_, String

        filters = [AuditLogModel.tenant_id == tenant_id]
        if q and q.strip():
            like = f"%{q.strip()}%"
            filters.append(
                or_(
                    AuditLogModel.action.ilike(like),
                    AuditLogModel.resource_type.ilike(like),
                    AuditLogModel.resource_id.ilike(like),
                    cast(AuditLogModel.details, String).ilike(like),
                )
            )
        total = int(self._db.scalar(select(func.count()).select_from(AuditLogModel).where(*filters)) or 0)
        rows = list(
            self._db.scalars(
                select(AuditLogModel)
                .where(*filters)
                .order_by(AuditLogModel.id.desc())
                .offset(max(0, offset))
                .limit(limit)
            ).all()
        )
        return rows, total

    def delete_all_for_tenant(self, tenant_id: int) -> int:
        from sqlalchemy import delete

        result = self._db.execute(delete(AuditLogModel).where(AuditLogModel.tenant_id == tenant_id))
        self._db.flush()
        return int(result.rowcount or 0)
