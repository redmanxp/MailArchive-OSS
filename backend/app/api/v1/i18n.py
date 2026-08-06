"""Public i18n endpoints — language discovery and packs for the whole app."""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user, require_roles
from app.config import Settings, get_settings
from app.domain.enums.roles import UserRole
from app.i18n import get_pack, list_locales, normalize_locale
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/i18n", tags=["i18n"])

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LocaleOption(BaseModel):
    code: str
    name: str


class LocaleListResponse(BaseModel):
    locales: list[LocaleOption]
    default_locale: str = "es"


class LocalePackResponse(BaseModel):
    code: str
    name: str
    ui: dict[str, Any] = Field(default_factory=dict)
    email: dict[str, Any] = Field(default_factory=dict)


class TenantLocaleUpdate(BaseModel):
    locale: str = Field(min_length=2, max_length=8)


class AppearancePublic(BaseModel):
    brand_name: str = ""
    primary_color: str = ""


class AppearanceUpdate(BaseModel):
    brand_name: str | None = Field(default=None, max_length=80)
    primary_color: str | None = Field(default=None, max_length=7)


def _settings_repo(db: Session, settings: Settings) -> SqlAlchemyTenantSettingsRepository:
    return SqlAlchemyTenantSettingsRepository(db, CredentialCipher(settings))


@router.get("/locales", response_model=LocaleListResponse)
def get_locales() -> LocaleListResponse:
    """Public: languages available (any new JSON under i18n/locales appears here)."""
    return LocaleListResponse(locales=[LocaleOption(**x) for x in list_locales()], default_locale="es")


@router.get("/appearance", response_model=AppearancePublic)
def get_appearance(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AppearancePublic:
    """Any authenticated user: org display name + primary color."""
    data = _settings_repo(db, settings).get_appearance(ctx.user.tenant_id)
    return AppearancePublic(**data)


@router.put("/appearance", response_model=AppearancePublic)
def update_appearance(
    body: AppearanceUpdate,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AppearancePublic:
    """Admin: update sidebar brand name and primary color (#RRGGBB or empty)."""
    color = body.primary_color
    if color is not None and color.strip() and not _HEX_COLOR.match(color.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="primary_color must be #RRGGBB or empty",
        )
    data = _settings_repo(db, settings).update_appearance(
        ctx.user.tenant_id,
        brand_name=body.brand_name,
        primary_color=color.strip() if color is not None else None,
    )
    return AppearancePublic(**data)


@router.put("/tenant-locale", response_model=MessageResponse)
def set_tenant_locale(
    body: TenantLocaleUpdate,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    """Admin: set application language for the whole tenant (UI + emails)."""
    code = normalize_locale(body.locale)
    available = {x["code"] for x in list_locales()}
    if code not in available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Locale not available")
    repo = _settings_repo(db, settings)
    repo.set_ui_locale(ctx.user.tenant_id, code)
    return MessageResponse(message=f"ui_locale={code}")


@router.get("/{code}", response_model=LocalePackResponse)
def get_locale_pack(code: str) -> LocalePackResponse:
    """Public: full UI + email strings for one language pack."""
    available = {x["code"] for x in list_locales()}
    normalized = normalize_locale(code)
    if code.strip().lower() not in available and normalized not in available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locale not found")
    pack = get_pack(normalized)
    return LocalePackResponse(code=pack["code"], name=pack["name"], ui=pack["ui"], email=pack["email"])
