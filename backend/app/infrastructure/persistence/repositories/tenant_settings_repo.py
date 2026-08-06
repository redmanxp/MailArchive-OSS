"""Tenant settings persistence (SMTP + email templates in JSON).

SMTP passwords are stored Fernet-encrypted under ``password_encrypted``.
``email_templates`` live in the same ``smtp_config`` JSON blob so one admin
PUT updates both relay settings and message copy.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.i18n import normalize_locale
from app.infrastructure.email.templates import (
    default_email_templates,
    merge_email_templates,
    save_locale_override,
)
from app.infrastructure.persistence.models import TenantSettingsModel
from app.infrastructure.security.fernet_cipher import CredentialCipher


class SqlAlchemyTenantSettingsRepository:
    def __init__(self, db: Session, cipher: CredentialCipher) -> None:
        self._db = db
        self._cipher = cipher

    def get(self, tenant_id: int) -> TenantSettingsModel | None:
        return self._db.scalar(
            select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == tenant_id)
        )

    def get_ui_locale(self, tenant_id: int) -> str:
        """Application language for the whole tenant (UI + outbound email)."""
        row = self.get(tenant_id)
        features = dict(row.features or {}) if row else {}
        return normalize_locale(features.get("ui_locale"))

    def set_ui_locale(self, tenant_id: int, locale: str) -> str:
        code = normalize_locale(locale)
        row = self.get(tenant_id)
        if row is None:
            row = TenantSettingsModel(tenant_id=tenant_id, features={}, smtp_config={})
            self._db.add(row)
            self._db.flush()
        features = dict(row.features or {})
        features["ui_locale"] = code
        row.features = features
        # Keep email active_locale aligned with app language.
        smtp = dict(row.smtp_config or {})
        et = dict(smtp.get("email_templates") or {})
        et["active_locale"] = code
        smtp["email_templates"] = et
        row.smtp_config = smtp
        self._db.flush()
        return code

    def get_smtp_public(self, tenant_id: int) -> dict:
        """Settings for the admin UI (no password; templates always merged with defaults)."""
        row = self.get(tenant_id)
        ui_locale = self.get_ui_locale(tenant_id)
        if not row or not row.smtp_config:
            return {"email_templates": default_email_templates(ui_locale), "ui_locale": ui_locale}
        cfg = dict(row.smtp_config)
        cfg.pop("password_encrypted", None)
        cfg["configured"] = bool(cfg.get("host") and cfg.get("user"))
        cfg["email_templates"] = merge_email_templates(cfg.get("email_templates"), ui_locale)
        cfg["ui_locale"] = ui_locale
        return cfg

    def get_smtp_runtime(self, tenant_id: int) -> dict | None:
        """Decrypt password for SmtpNotifier, or None if SMTP is disabled / incomplete."""
        row = self.get(tenant_id)
        if not row or not row.smtp_config:
            return None
        cfg = dict(row.smtp_config)
        enc = cfg.pop("password_encrypted", None)
        if enc:
            try:
                cfg["password"] = self._cipher.decrypt_dict({"p": enc})["p"]
            except ValueError:
                cfg["password"] = ""
        else:
            cfg["password"] = cfg.get("password", "")
        if not cfg.get("enabled", True):
            return None
        if not cfg.get("host") or not cfg.get("user"):
            return None
        ui_locale = self.get_ui_locale(tenant_id)
        cfg["email_templates"] = merge_email_templates(cfg.get("email_templates"), ui_locale)
        return cfg

    def update_smtp(self, tenant_id: int, payload: dict) -> dict:
        """Upsert SMTP fields; encrypt password when provided; merge email_templates."""
        row = self.get(tenant_id)
        if row is None:
            row = TenantSettingsModel(tenant_id=tenant_id, smtp_config={})
            self._db.add(row)
            self._db.flush()

        current = dict(row.smtp_config or {})
        for key in ("host", "port", "user", "from_email", "from_name", "starttls", "enabled"):
            if key in payload and payload[key] is not None:
                current[key] = payload[key]

        if payload.get("email_templates") is not None:
            # Keep multi-locale map; merge editor payload for the active locale.
            current["email_templates"] = save_locale_override(
                current.get("email_templates")
                if isinstance(current.get("email_templates"), dict)
                else None,
                payload["email_templates"],
            )

        if payload.get("password"):
            current["password_encrypted"] = self._cipher.encrypt_dict({"p": payload["password"]})
            current.pop("password", None)

        row.smtp_config = current
        self._db.flush()
        return self.get_smtp_public(tenant_id)
