"""Public branding assets + admin logo upload."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, require_roles
from app.config import Settings, get_settings
from app.domain.enums.roles import UserRole
from app.infrastructure import branding_storage
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import TenantModel
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/branding", tags=["branding"])

Kind = Literal["icon", "full"]


def _first_tenant_id(db: Session) -> int | None:
    row = db.scalar(select(TenantModel).order_by(TenantModel.id.asc()).limit(1))
    return int(row.id) if row else None


def _parse_kind(kind: str) -> Kind:
    if kind not in ("icon", "full"):
        raise HTTPException(status_code=404, detail="Not found")
    return kind  # type: ignore[return-value]


@router.get("/logo/{kind}")
def get_logo(
    kind: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Public: custom tenant logo or built-in default (install/login friendly)."""
    k = _parse_kind(kind)
    tenant_id = _first_tenant_id(db)
    path = branding_storage.resolve_logo_path(settings, tenant_id, k)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.post("/logo/{kind}", response_model=MessageResponse)
async def upload_logo(
    kind: str,
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(...)],
) -> MessageResponse:
    k = _parse_kind(kind)
    raw = await file.read()
    try:
        branding_storage.save_logo(
            settings,
            ctx.user.tenant_id,
            k,
            raw,
            file.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message=f"logo_{k}_updated")


@router.delete("/logo/{kind}", response_model=MessageResponse)
def reset_logo(
    kind: str,
    ctx: Annotated[CurrentUserContext, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    k = _parse_kind(kind)
    branding_storage.delete_custom_logo(settings, ctx.user.tenant_id, k)
    return MessageResponse(message=f"logo_{k}_reset")
