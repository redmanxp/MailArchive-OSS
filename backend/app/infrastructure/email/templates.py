"""Email templates: defaults from app i18n packs + optional tenant overrides.

App language packs live in ``app/i18n/locales/*.json`` (UI + email together).
Tenant overrides for email copy stay under ``smtp_config.email_templates``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.i18n import get_email_templates as pack_email_templates
from app.i18n import list_locales, normalize_locale

logger = logging.getLogger(__name__)

_TEMPLATE_FIELDS = (
    "subject",
    "greeting",
    "intro",
    "button_label",
    "footer",
    "link_fallback",
)


def list_available_locales() -> list[dict[str, str]]:
    """Language packs discovered on disk (same list as UI languages)."""
    return list_locales()


def default_email_templates(locale: str | None = None) -> dict[str, Any]:
    return pack_email_templates(locale)


def _legacy_flat_override(stored: dict) -> dict[str, Any] | None:
    if "invite" in stored or "reset" in stored:
        return {
            "invite": stored.get("invite") if isinstance(stored.get("invite"), dict) else {},
            "reset": stored.get("reset") if isinstance(stored.get("reset"), dict) else {},
        }
    return None


def merge_email_templates(stored: dict | None, locale: str | None = None) -> dict[str, Any]:
    """Disk pack for locale + tenant overrides for that locale."""
    stored = stored or {}
    active = normalize_locale(
        stored.get("active_locale") or stored.get("locale") or locale
    )
    base = default_email_templates(active)

    override: dict[str, Any] | None = None
    locales_map = stored.get("locales")
    if isinstance(locales_map, dict) and isinstance(locales_map.get(active), dict):
        override = locales_map[active]
    elif normalize_locale(stored.get("locale")) == active:
        override = _legacy_flat_override(stored)

    if override:
        for kind in ("invite", "reset"):
            block = override.get(kind) or {}
            if isinstance(block, dict):
                for key, value in block.items():
                    if key in _TEMPLATE_FIELDS and isinstance(value, str) and value.strip():
                        base[kind][key] = value

    base["locale"] = active
    return base


def save_locale_override(stored: dict | None, templates: dict) -> dict[str, Any]:
    """Persist editor output into multi-locale map + active_locale."""
    current = dict(stored or {})
    locales_map = dict(current.get("locales") or {})
    active = normalize_locale(templates.get("locale") or current.get("active_locale"))
    locales_map[active] = {
        "invite": dict(templates.get("invite") or {}),
        "reset": dict(templates.get("reset") or {}),
    }
    current.pop("invite", None)
    current.pop("reset", None)
    current.pop("locale", None)
    current["active_locale"] = active
    current["locales"] = locales_map
    return current


def render_template(text: str, **vars: str) -> str:
    out = text
    for key, value in vars.items():
        out = out.replace("{" + key + "}", value)
    return out
