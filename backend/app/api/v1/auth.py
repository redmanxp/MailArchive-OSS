"""Auth endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.rate_limit import enforce_rate_limit
from app.api.deps.auth import (
    CurrentUserContext,
    get_client_meta,
    get_current_user,
    get_password_hasher,
    get_token_service,
    map_domain_error,
)
from app.application.use_cases.auth.auth_use_cases import (
    ChangePasswordUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
)
from app.application.use_cases.users.user_management import (
    CompletePasswordLinkUseCase,
    PreviewPasswordLinkUseCase,
    SelfRegisterUseCase,
    UpdateOwnProfileUseCase,
)
from app.config import Settings, get_settings
from app.domain.exceptions import DomainError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyInstallRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure.security.jwt_service import JwtTokenService
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    CompletePasswordLinkRequest,
    CompletePasswordLinkResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordLinkPreviewResponse,
    RefreshRequest,
    SelfRegisterRequest,
    SelfRegisterResponse,
    TokenResponse,
    UpdateOwnProfileRequest,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=SelfRegisterResponse)
def self_register(
    body: SelfRegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SelfRegisterResponse:
    """Alta pública: crea usuario o envía enlace de recuperación si el email ya existe."""
    if not settings.feature_public_register:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El registro público está deshabilitado. Pedí acceso a un administrador.",
        )
    enforce_rate_limit(request, "auth.register", settings)
    uc = SelfRegisterUseCase(
        tenant_repo=SqlAlchemyTenantRepository(db),
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings_repo=SqlAlchemyTenantSettingsRepository(db, CredentialCipher(settings)),
        settings=settings,
    )
    try:
        result = uc.execute(
            tenant_slug=body.tenant_slug or settings.install_tenant_slug,
            name=body.name,
            email=str(body.email),
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return SelfRegisterResponse(
        id=result["id"],
        name=result["name"],
        email=result["email"],
        role=result["role"],
        email_sent=result["email_sent"],
        email_detail=result.get("email_detail", ""),
        action=result.get("action", "created"),
        message=result.get("message", "Revisá tu correo."),
    )


@router.get("/password-link", response_model=PasswordLinkPreviewResponse)
def preview_password_link(
    token: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasswordLinkPreviewResponse:
    uc = PreviewPasswordLinkUseCase(SqlAlchemyUserRepository(db), settings)
    try:
        result = uc.execute(token)
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return PasswordLinkPreviewResponse(**result)


@router.post("/password-link/complete", response_model=CompletePasswordLinkResponse)
def complete_password_link(
    body: CompletePasswordLinkRequest,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CompletePasswordLinkResponse:
    uc = CompletePasswordLinkUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings=settings,
    )
    try:
        result = uc.execute(token=body.token, new_password=body.new_password)
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return CompletePasswordLinkResponse(**result)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[JwtTokenService, Depends(get_token_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    enforce_rate_limit(request, "auth.login", settings)
    ip, ua = get_client_meta(request)
    uc = LoginUseCase(
        install_repo=SqlAlchemyInstallRepository(db),
        tenant_repo=SqlAlchemyTenantRepository(db),
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        token_service=tokens,
        refresh_repo=SqlAlchemyRefreshTokenRepository(db),
        audit_repo=SqlAlchemyAuditLogRepository(db),
        settings=settings,
    )
    try:
        result = uc.execute(
            email=str(body.email),
            password=body.password,
            tenant_slug=body.tenant_slug,
            ip=ip,
            user_agent=ua,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    tokens: Annotated[JwtTokenService, Depends(get_token_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    ip, ua = get_client_meta(request)
    uc = RefreshTokenUseCase(
        token_service=tokens,
        refresh_repo=SqlAlchemyRefreshTokenRepository(db),
        user_repo=SqlAlchemyUserRepository(db),
        settings=settings,
    )
    try:
        result = uc.execute(body.refresh_token, ip=ip, user_agent=ua)
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return TokenResponse(**result)


@router.post("/logout", response_model=MessageResponse)
def logout(
    body: LogoutRequest,
    db: Annotated[Session, Depends(get_db)],
    tokens: Annotated[JwtTokenService, Depends(get_token_service)],
) -> MessageResponse:
    uc = LogoutUseCase(token_service=tokens, refresh_repo=SqlAlchemyRefreshTokenRepository(db))
    uc.execute(body.refresh_token)
    return MessageResponse(message="Sesión cerrada")


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> ChangePasswordResponse:
    ip, ua = get_client_meta(request)
    uc = ChangePasswordUseCase(
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        refresh_repo=SqlAlchemyRefreshTokenRepository(db),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            current_password=body.current_password,
            new_password=body.new_password,
            ip=ip,
            user_agent=ua,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ChangePasswordResponse(**result)


@router.patch("/me", response_model=UserPublic)
def update_me(
    body: UpdateOwnProfileRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> UserPublic:
    uc = UpdateOwnProfileUseCase(
        SqlAlchemyUserRepository(db),
        SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            name=body.name,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return UserPublic(**result)


@router.get("/me", response_model=UserPublic)
def me(ctx: Annotated[CurrentUserContext, Depends(get_current_user)]) -> UserPublic:
    u = ctx.user
    return UserPublic(
        id=u.id,
        tenant_id=u.tenant_id,
        name=u.name,
        email=u.email,
        role=u.role.value,
        must_change_password=u.must_change_password,
    )
