"""Tenant branding assets (logos) on the filesystem.

Defaults ship under ``app/static/branding/``. Custom uploads live under
``{storage_root}/_branding/{tenant_id}/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)

_STATIC = Path(__file__).resolve().parents[1] / "static" / "branding"
_ALLOWED = {"image/png", "image/jpeg", "image/webp"}
_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB


def default_logo_path(kind: str) -> Path:
    name = "logo-icon.png" if kind == "icon" else "logo-full.png"
    return _STATIC / name


def custom_logo_dir(settings: Settings, tenant_id: int) -> Path:
    return Path(settings.storage_root) / "_branding" / str(tenant_id)


def custom_logo_path(settings: Settings, tenant_id: int, kind: str) -> Path:
    name = "logo-icon.png" if kind == "icon" else "logo-full.png"
    return custom_logo_dir(settings, tenant_id) / name


def resolve_logo_path(settings: Settings, tenant_id: int | None, kind: str) -> Path:
    if tenant_id is not None:
        custom = custom_logo_path(settings, tenant_id, kind)
        if custom.is_file():
            return custom
    return default_logo_path(kind)


def has_custom_logo(settings: Settings, tenant_id: int, kind: str) -> bool:
    return custom_logo_path(settings, tenant_id, kind).is_file()


def save_logo(settings: Settings, tenant_id: int, kind: str, data: bytes, content_type: str) -> Path:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in _ALLOWED:
        raise ValueError("Only PNG, JPEG or WebP logos are allowed")
    if len(data) > _MAX_BYTES:
        raise ValueError("Logo file too large (max 2 MB)")
    if len(data) < 32:
        raise ValueError("Invalid image file")

    dest_dir = custom_logo_dir(settings, tenant_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = custom_logo_path(settings, tenant_id, kind)

    try:
        from io import BytesIO

        from PIL import Image

        opened = Image.open(BytesIO(data))
        im = opened.convert("RGBA")
        # Cap dimension for storage/UI
        max_side = 1024 if kind == "full" else 512
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        im.save(dest, "PNG", optimize=True)
    except Exception as exc:
        logger.exception("Could not process logo upload")
        raise ValueError(f"Could not read image: {exc}") from exc

    logger.info("Saved branding logo tenant=%s kind=%s path=%s", tenant_id, kind, dest)
    return dest


def delete_custom_logo(settings: Settings, tenant_id: int, kind: str) -> bool:
    path = custom_logo_path(settings, tenant_id, kind)
    if path.is_file():
        path.unlink()
        logger.info("Removed custom logo tenant=%s kind=%s", tenant_id, kind)
        return True
    return False
