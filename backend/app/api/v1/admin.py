"""Admin endpoints — users, settings, audit."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import (
    CurrentUserContext,
    get_client_meta,
    get_password_hasher,
    map_domain_error,
    require_roles,
)
from app.application.use_cases.users.user_management import (
    CreateUserUseCase,
    DeactivateUserUseCase,
    GetSmtpSettingsUseCase,
    ResetPasswordUseCase,
    TestSmtpSettingsUseCase,
    UpdateSmtpSettingsUseCase,
    UpdateUserUseCase,
)
from app.config import Settings, get_settings
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import DomainError, ValidationError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import TenantModel
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.schemas.admin import (
    CreateUserRequest,
    CreateUserResponse,
    ResetPasswordRequest,
    SmtpSettingsPublic,
    SmtpSettingsUpdate,
    SmtpTestRequest,
    SmtpTestResponse,
    UpdateUserRequest,
    UserAdminPublic,
)
from app.schemas.auth import MessageResponse, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditLogItem(BaseModel):
    id: int
    action: str
    user_id: int | None
    resource_type: str | None
    resource_id: str | None
    details: dict | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int = 0
    limit: int = 50
    offset: int = 0


def _settings_repo(db: Session, settings: Settings) -> SqlAlchemyTenantSettingsRepository:
    return SqlAlchemyTenantSettingsRepository(db, CredentialCipher(settings))


def _tenant_slug(db: Session, tenant_id: int) -> str:
    row = db.get(TenantModel, tenant_id)
    return row.slug if row else "obrasociales"


@router.get("/users", response_model=list[UserAdminPublic])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> list[UserAdminPublic]:
    users = SqlAlchemyUserRepository(db).list_by_tenant(ctx.user.tenant_id)
    return [
        UserAdminPublic(
            id=u.id,
            tenant_id=u.tenant_id,
            name=u.name,
            email=u.email,
            role=u.role.value,
            status=u.status.value,
            must_change_password=u.must_change_password,
        )
        for u in users
    ]


@router.post("/users", response_model=CreateUserResponse)
def create_user(
    body: CreateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CreateUserResponse:
    try:
        role = UserRole(body.role)
    except ValueError as exc:
        raise map_domain_error(ValidationError(f"Rol inválido: {body.role}")) from exc
    uc = CreateUserUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings_repo=_settings_repo(db, settings),
        settings=settings,
        tenant_slug=_tenant_slug(db, ctx.user.tenant_id),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            name=body.name,
            email=str(body.email),
            role=role,
            password=body.password,
            must_change_password=body.must_change_password if body.password else True,
            send_welcome_email=body.send_welcome_email,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return CreateUserResponse(**result)


@router.patch("/users/{user_id}", response_model=UserAdminPublic)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> UserAdminPublic:
    try:
        role = UserRole(body.role) if body.role else None
        status = UserStatus(body.status) if body.status else None
    except ValueError as exc:
        raise map_domain_error(ValidationError(str(exc))) from exc
    uc = UpdateUserUseCase(SqlAlchemyUserRepository(db), SqlAlchemyAuditLogRepository(db))
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            name=body.name,
            role=role,
            status=status,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return UserAdminPublic(
        id=result["id"],
        tenant_id=ctx.user.tenant_id,
        name=result["name"],
        email=result["email"],
        role=result["role"],
        status=result["status"],
        must_change_password=result["must_change_password"],
    )


@router.post("/users/{user_id}/reset-password", response_model=dict)
def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    uc = ResetPasswordUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings_repo=_settings_repo(db, settings),
        settings=settings,
    )
    try:
        return uc.execute(
            tenant_id=ctx.user.tenant_id,
            actor_user_id=ctx.user.id,
            user_id=user_id,
            new_password=body.new_password,
            must_change_password=body.must_change_password if body.new_password else True,
            send_email=body.send_email,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc


@router.post("/users/{user_id}/deactivate", response_model=MessageResponse)
def deactivate_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> MessageResponse:
    uc = DeactivateUserUseCase(SqlAlchemyUserRepository(db), SqlAlchemyAuditLogRepository(db))
    try:
        uc.execute(tenant_id=ctx.user.tenant_id, actor_user_id=ctx.user.id, user_id=user_id)
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return MessageResponse(message="Usuario desactivado")


@router.get("/settings/smtp", response_model=SmtpSettingsPublic)
def get_smtp_settings(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpSettingsPublic:
    data = GetSmtpSettingsUseCase(_settings_repo(db, settings)).execute(ctx.user.tenant_id)
    defaults = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "from_email": settings.smtp_from or settings.smtp_user,
        "from_name": settings.app_name,
        "starttls": settings.smtp_tls,
        "enabled": bool(settings.smtp_host),
        "configured": bool(settings.smtp_host and settings.smtp_user),
    }
    merged = {**defaults, **data}
    return SmtpSettingsPublic(**merged)


@router.put("/settings/smtp", response_model=SmtpSettingsPublic)
def update_smtp_settings(
    body: SmtpSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpSettingsPublic:
    uc = UpdateSmtpSettingsUseCase(_settings_repo(db, settings), SqlAlchemyAuditLogRepository(db))
    payload = body.model_dump(exclude_unset=True)
    result = uc.execute(tenant_id=ctx.user.tenant_id, actor_user_id=ctx.user.id, payload=payload)
    defaults = {"host": "", "port": 587, "user": "", "from_email": "", "from_name": "MailArchive", "starttls": True, "enabled": True, "configured": False}
    merged = {**defaults, **result}
    return SmtpSettingsPublic(**merged)


@router.post("/settings/smtp/test", response_model=SmtpTestResponse)
def test_smtp_settings(
    body: SmtpTestRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SmtpTestResponse:
    uc = TestSmtpSettingsUseCase(_settings_repo(db, settings), settings)
    payload = body.model_dump(exclude_unset=True) if body else None
    result = uc.execute(ctx.user.tenant_id, payload if (payload and payload.get("host")) else None)
    return SmtpTestResponse(**result)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    rows, total = SqlAlchemyAuditLogRepository(db).search(
        ctx.user.tenant_id, q=q, limit=limit, offset=offset
    )
    return AuditLogListResponse(
        items=[
            AuditLogItem(
                id=r.id,
                action=r.action,
                user_id=r.user_id,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                details=r.details,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/audit-logs", response_model=MessageResponse)
def clear_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
) -> MessageResponse:
    repo = SqlAlchemyAuditLogRepository(db)
    deleted = repo.delete_all_for_tenant(ctx.user.tenant_id)
    repo.add(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        action="audit.clear_all",
        resource_type="audit_logs",
        details={"deleted": deleted},
    )
    return MessageResponse(message=f"Se borraron {deleted} registros de auditoría.")
