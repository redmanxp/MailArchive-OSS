"""Persistent system overrides (DB / storage / Microsoft) outside .env.

Stored as JSON under ``/data/system_overrides.json`` (Docker) or ``backend/data/``.
Secrets are Fernet-encrypted with ``DATA_ENCRYPTION_KEY``.
DB engine changes require an API process restart to take effect.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import ROOT_DIR, Settings

logger = logging.getLogger(__name__)

PUBLIC_KEYS = (
    "storage_root",
    "storage_backend",
    "s3_endpoint_url",
    "s3_access_key",
    "s3_bucket",
    "s3_region",
    "s3_force_path_style",
    "s3_prefix",
    "db_engine",
    "mysql_host",
    "mysql_port",
    "mysql_user",
    "mysql_database",
    "microsoft_client_id",
    "microsoft_tenant_id",
    "microsoft_redirect_uri",
    "tenant_mode",
)
SECRET_PLAIN = ("mysql_password", "microsoft_client_secret", "s3_secret_key")


def overrides_path() -> Path:
    env = os.environ.get("SYSTEM_OVERRIDES_PATH", "").strip()
    if env:
        return Path(env)
    docker_data = Path("/data")
    if docker_data.is_dir() and os.access(docker_data, os.W_OK):
        return docker_data / "system_overrides.json"
    path = ROOT_DIR / "data" / "system_overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _fernet(settings: Settings) -> Fernet | None:
    try:
        return Fernet(settings.data_encryption_key.encode("utf-8"))
    except Exception:
        logger.warning("Cannot init Fernet for system overrides")
        return None


def _encrypt(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(fernet: Fernet, token: str) -> str:
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt system override secret") from exc


def load_raw() -> dict[str, Any]:
    path = overrides_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading system overrides %s: %s", path, exc)
        return {}


def save_raw(data: dict[str, Any]) -> None:
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _strip_str(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def apply_overrides(settings: Settings) -> Settings:
    """Return settings with file overrides merged (secrets decrypted)."""
    raw = load_raw()
    if not raw:
        return settings
    updates: dict[str, Any] = {}
    for key in PUBLIC_KEYS:
        if key in raw and raw[key] is not None:
            updates[key] = _strip_str(raw[key])
    fernet = _fernet(settings)
    if fernet:
        if raw.get("mysql_password_encrypted"):
            try:
                updates["mysql_password"] = _decrypt(fernet, raw["mysql_password_encrypted"])
            except ValueError:
                logger.error("mysql_password override decrypt failed")
        if raw.get("microsoft_client_secret_encrypted"):
            try:
                updates["microsoft_client_secret"] = _decrypt(
                    fernet, raw["microsoft_client_secret_encrypted"]
                )
            except ValueError:
                logger.error("microsoft_client_secret override decrypt failed")
        if raw.get("s3_secret_key_encrypted"):
            try:
                updates["s3_secret_key"] = _decrypt(fernet, raw["s3_secret_key_encrypted"]).strip()
            except ValueError:
                logger.error("s3_secret_key override decrypt failed")
    if updates.get("db_engine") == "mysql":
        updates["database_url"] = None
    if not updates:
        return settings
    return settings.model_copy(update=updates)


def restart_required_for_db(current: Settings, payload: dict[str, Any]) -> bool:
    """True if payload changes DB connectivity vs currently running settings."""
    engine = payload.get("db_engine", current.db_engine)
    if engine != current.db_engine:
        return True
    if engine == "mysql":
        for key, attr in (
            ("mysql_host", current.mysql_host),
            ("mysql_port", current.mysql_port),
            ("mysql_user", current.mysql_user),
            ("mysql_database", current.mysql_database),
        ):
            if key in payload and payload[key] is not None and payload[key] != attr:
                return True
        if payload.get("mysql_password"):
            return True
    if engine == "sqlite" and current.db_engine != "sqlite":
        return True
    return False


def update_system_overrides(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge payload into overrides file. Returns public view + restart_required."""
    raw = load_raw()
    for key in (
        "storage_root",
        "storage_backend",
        "s3_endpoint_url",
        "s3_access_key",
        "s3_bucket",
        "s3_region",
        "s3_force_path_style",
        "s3_prefix",
        "db_engine",
        "mysql_host",
        "mysql_port",
        "mysql_user",
        "mysql_database",
        "tenant_mode",
    ):
        if key in payload and payload[key] is not None:
            raw[key] = _strip_str(payload[key])

    fernet = _fernet(settings)
    if payload.get("mysql_password") and fernet:
        raw["mysql_password_encrypted"] = _encrypt(fernet, str(payload["mysql_password"]).strip())
    if payload.get("s3_secret_key") and fernet:
        raw["s3_secret_key_encrypted"] = _encrypt(fernet, str(payload["s3_secret_key"]).strip())

    need_restart = restart_required_for_db(settings, payload)
    raw["restart_required"] = bool(raw.get("restart_required")) or need_restart
    # Clear restart flag only when caller asks after a successful restart detection
    if payload.get("clear_restart_flag"):
        raw["restart_required"] = False

    save_raw(raw)
    return public_system_view(settings)


def update_microsoft_overrides(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    raw = load_raw()
    for key in ("microsoft_client_id", "microsoft_tenant_id", "microsoft_redirect_uri"):
        if key in payload and payload[key] is not None:
            raw[key] = payload[key]
    fernet = _fernet(settings)
    if payload.get("microsoft_client_secret") and fernet:
        raw["microsoft_client_secret_encrypted"] = _encrypt(
            fernet, payload["microsoft_client_secret"]
        )
    save_raw(raw)
    return public_microsoft_view(settings)


def public_system_view(settings: Settings) -> dict[str, Any]:
    """Build response from live settings + restart flag in file."""
    raw = load_raw()
    engine = (settings.db_engine or "sqlite").lower()
    if engine == "sqlite":
        url = settings.build_database_url()
        label = url.split("sqlite:///")[-1] if "sqlite" in url else url
        mysql_host = None
        mysql_port = None
        mysql_database = None
    else:
        label = settings.mysql_database
        mysql_host = settings.mysql_host
        mysql_port = settings.mysql_port
        mysql_database = settings.mysql_database
    return {
        "app_env": settings.app_env,
        "db_engine": engine,
        "database_label": label,
        "mysql_host": mysql_host,
        "mysql_port": mysql_port,
        "mysql_database": mysql_database,
        "mysql_user": settings.mysql_user if engine != "sqlite" else None,
        "storage_root": settings.storage_root,
        "storage_backend": (settings.storage_backend or "filesystem").lower(),
        "s3_endpoint_url": settings.s3_endpoint_url or "",
        "s3_access_key": settings.s3_access_key or "",
        "s3_bucket": settings.s3_bucket or "",
        "s3_region": settings.s3_region or "us-east-1",
        "s3_force_path_style": bool(settings.s3_force_path_style),
        "s3_prefix": settings.s3_prefix or "",
        "s3_secret_set": bool(raw.get("s3_secret_key_encrypted") or settings.s3_secret_key),
        "editable": True,
        "restart_required": bool(raw.get("restart_required")),
        "mysql_password_set": bool(raw.get("mysql_password_encrypted") or settings.mysql_password),
        "tenant_mode": normalize_tenant_mode(
            raw.get("tenant_mode") or getattr(settings, "tenant_mode", None) or "single"
        ),
    }


def normalize_tenant_mode(value: str | None) -> str:
    mode = (value or "single").strip().lower()
    return mode if mode in ("single", "multi") else "single"


def public_microsoft_view(settings: Settings) -> dict[str, Any]:
    raw = load_raw()
    return {
        "client_id": settings.microsoft_client_id or "",
        "tenant_id": settings.microsoft_tenant_id or "common",
        "redirect_uri": settings.microsoft_redirect_uri or "",
        "configured": bool(settings.microsoft_client_id and settings.microsoft_client_secret),
        "secret_set": bool(
            raw.get("microsoft_client_secret_encrypted") or settings.microsoft_client_secret
        ),
    }


def clear_restart_flag() -> None:
    raw = load_raw()
    if raw.get("restart_required"):
        raw["restart_required"] = False
        save_raw(raw)
