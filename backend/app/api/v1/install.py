"""Install wizard: org + admin + data location (DB / storage)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.rate_limit import enforce_rate_limit
from app.api.deps.auth import get_client_meta, get_password_hasher, map_domain_error
from app.application.use_cases.install.bootstrap import (
    BootstrapInstallationUseCase,
    GetInstallationStatusUseCase,
)
from app.config import Settings, get_settings, reload_settings
from app.domain.exceptions import DomainError
from app.infrastructure import system_overrides
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
def install_status(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InstallStatusResponse:
    from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
    from app.infrastructure.security.fernet_cipher import CredentialCipher

    uc = GetInstallationStatusUseCase(SqlAlchemyInstallRepository(db))
    data = uc.execute()
    ui_locale = "es"
    if data["installed"]:
        from sqlalchemy import select
        from app.infrastructure.persistence.models import TenantModel

        row = db.scalar(select(TenantModel).order_by(TenantModel.id.asc()).limit(1))
        if row:
            ui_locale = SqlAlchemyTenantSettingsRepository(db, CredentialCipher(settings)).get_ui_locale(
                row.id
            )
    raw = system_overrides.load_raw()
    return InstallStatusResponse(
        installed=data["installed"],
        public_register_enabled=settings.feature_public_register,
        ui_locale=ui_locale,
        db_engine=(settings.db_engine or "sqlite").lower(),
        storage_root=settings.storage_root,
        restart_required=bool(raw.get("restart_required")),
    )


@router.post("", response_model=InstallResponse)
def install(
    body: InstallRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InstallResponse:
    enforce_rate_limit(request, "install", settings)
    ip, ua = get_client_meta(request)

    # Persist data preferences from the install wizard before bootstrap.
    data_payload: dict = {}
    if body.storage_root:
        data_payload["storage_root"] = body.storage_root.strip()
    if body.db_engine:
        eng = body.db_engine.strip().lower()
        if eng not in ("sqlite", "mysql"):
            raise HTTPException(status_code=400, detail="db_engine must be sqlite or mysql")
        data_payload["db_engine"] = eng
        if eng == "mysql":
            for key, val in (
                ("mysql_host", body.mysql_host),
                ("mysql_port", body.mysql_port),
                ("mysql_user", body.mysql_user),
                ("mysql_database", body.mysql_database),
                ("mysql_password", body.mysql_password),
            ):
                if val is not None and val != "":
                    data_payload[key] = val
    if data_payload:
        need_restart = system_overrides.restart_required_for_db(settings, data_payload)
        system_overrides.update_system_overrides(settings, data_payload)
        if need_restart:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Se guardó la configuración de base de datos. "
                    "Reiniciá la API (docker compose restart api) y volvé a abrir la instalación."
                ),
            )
        reload_settings()

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
