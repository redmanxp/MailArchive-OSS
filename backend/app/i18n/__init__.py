"""Application language packs (UI + email) discovered from JSON files.

Drop ``backend/app/i18n/locales/<code>.json`` (same shape as ``es.json``) and the
language appears automatically in the admin Language tab — no code change.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LOCALE = "es"

_EMAIL_FIELDS = (
    "subject",
    "greeting",
    "intro",
    "button_label",
    "footer",
    "link_fallback",
)


def _read_pack(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Invalid locale pack: %s", path)
        return None
    if not isinstance(data, dict):
        return None
    code = str(data.get("code") or path.stem).strip().lower()
    name = str(data.get("name") or code).strip() or code
    ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
    email = data.get("email") if isinstance(data.get("email"), dict) else {}
    invite = email.get("invite") if isinstance(email.get("invite"), dict) else {}
    reset = email.get("reset") if isinstance(email.get("reset"), dict) else {}
    return {
        "code": code,
        "name": name,
        "ui": deepcopy(ui),
        "email": {
            "invite": {k: str(invite.get(k, "")) for k in _EMAIL_FIELDS},
            "reset": {k: str(reset.get(k, "")) for k in _EMAIL_FIELDS},
        },
    }


def discover_packs() -> list[dict[str, Any]]:
    if not LOCALES_DIR.is_dir():
        logger.warning("i18n locales directory missing: %s", LOCALES_DIR)
        return []
    packs: list[dict[str, Any]] = []
    for path in sorted(LOCALES_DIR.glob("*.json")):
        pack = _read_pack(path)
        if pack:
            packs.append(pack)
    return packs


def list_locales() -> list[dict[str, str]]:
    return [{"code": p["code"], "name": p["name"]} for p in discover_packs()]


def normalize_locale(locale: str | None) -> str:
    codes = {p["code"] for p in discover_packs()}
    if not codes:
        return DEFAULT_LOCALE
    if not locale:
        return DEFAULT_LOCALE if DEFAULT_LOCALE in codes else sorted(codes)[0]
    code = locale.strip().lower()[:8]
    if code in codes:
        return code
    return DEFAULT_LOCALE if DEFAULT_LOCALE in codes else sorted(codes)[0]


def get_pack(locale: str | None = None) -> dict[str, Any]:
    code = normalize_locale(locale)
    for pack in discover_packs():
        if pack["code"] == code:
            return deepcopy(pack)
    return {
        "code": code,
        "name": code,
        "ui": {},
        "email": {
            "invite": {k: "" for k in _EMAIL_FIELDS},
            "reset": {k: "" for k in _EMAIL_FIELDS},
        },
    }


def get_ui(locale: str | None = None) -> dict[str, Any]:
    return get_pack(locale).get("ui") or {}


def get_email_templates(locale: str | None = None) -> dict[str, Any]:
    pack = get_pack(locale)
    return {
        "locale": pack["code"],
        "invite": deepcopy(pack["email"]["invite"]),
        "reset": deepcopy(pack["email"]["reset"]),
    }
