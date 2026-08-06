"""API dependencies: auth, RBAC, DI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.entities.user import User
from app.domain.enums.roles import UserRole
from app.domain.exceptions import AuthenticationError, AuthorizationError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyUserRepository,
)
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_service import JwtTokenService

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUserContext:
    user: User
    token_claims: dict


def get_client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> JwtTokenService:
    return JwtTokenService(settings)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
) -> CurrentUserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    try:
        claims = token_service.decode_token(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acceso inválido")

    tenant_id = int(claims["tenant_id"])
    user_id = int(claims["sub"])
    user_repo = SqlAlchemyUserRepository(db)
    user = user_repo.get_by_id(tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

    # Gate: si debe cambiar password, solo permitir change-password y me
    path = request.url.path
    allowed_when_must_change = {
        "/api/v1/auth/change-password",
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
    }
    # PATCH /me also allowed (same path as GET /me)
    if user.must_change_password and path not in allowed_when_must_change:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe cambiar la contraseña antes de continuar",
        )

    return CurrentUserContext(user=user, token_claims=claims)


def require_roles(*roles: UserRole) -> Callable:
    allowed = set(roles)

    def _dependency(
        ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    ) -> CurrentUserContext:
        if ctx.user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta acción",
            )
        return ctx

    return _dependency


def map_domain_error(exc: Exception) -> HTTPException:
    from app.domain.exceptions import (
        AlreadyInstalledError,
        AuthenticationError as AuthErr,
        AuthorizationError as AuthzErr,
        NotInstalledError,
        NotFoundError,
        ValidationError,
    )

    if isinstance(exc, AlreadyInstalledError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, NotInstalledError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, AuthErr):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, (AuthzErr, AuthorizationError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    raise exc
