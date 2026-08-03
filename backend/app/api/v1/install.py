"""Install endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps.auth import get_client_meta, get_password_hasher, map_domain_error
from app.application.use_cases.install.bootstrap import (
    BootstrapInstallationUseCase,
    GetInstallationStatusUseCase,
)
from app.config import Settings, get_settings
from app.domain.exceptions import DomainError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyInstallRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.schemas.auth import InstallRequest, InstallResponse, InstallStatusResponse

router = APIRouter(prefix="/install", tags=["install"])


@router.get("/status", response_model=InstallStatusResponse)
def install_status(db: Annotated[Session, Depends(get_db)]) -> InstallStatusResponse:
    uc = GetInstallationStatusUseCase(SqlAlchemyInstallRepository(db))
    return InstallStatusResponse(**uc.execute())


@router.post("", response_model=InstallResponse)
def install(
    body: InstallRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InstallResponse:
    ip, ua = get_client_meta(request)
    uc = BootstrapInstallationUseCase(
        install_repo=SqlAlchemyInstallRepository(db),
        tenant_repo=SqlAlchemyTenantRepository(db),
        user_repo=SqlAlchemyUserRepository(db),
        password_hasher=hasher,
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_name=body.tenant_name or settings.install_tenant_name,
            tenant_slug=body.tenant_slug or settings.install_tenant_slug,
            admin_name=body.admin_name or settings.install_admin_name,
            admin_email=str(body.admin_email),
            admin_password=body.admin_password,
            ip=ip,
            user_agent=ua,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return InstallResponse(**result)
