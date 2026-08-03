"""Tenant settings repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def get_smtp_public(self, tenant_id: int) -> dict:
        row = self.get(tenant_id)
        if not row or not row.smtp_config:
            return {}
        cfg = dict(row.smtp_config)
        cfg.pop("password_encrypted", None)
        cfg["configured"] = bool(cfg.get("host") and cfg.get("user"))
        return cfg

    def get_smtp_runtime(self, tenant_id: int) -> dict | None:
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
        return cfg

    def update_smtp(self, tenant_id: int, payload: dict) -> dict:
        row = self.get(tenant_id)
        if row is None:
            row = TenantSettingsModel(tenant_id=tenant_id, smtp_config={})
            self._db.add(row)
            self._db.flush()

        current = dict(row.smtp_config or {})
        for key in ("host", "port", "user", "from_email", "from_name", "starttls", "enabled"):
            if key in payload and payload[key] is not None:
                current[key] = payload[key]

        if payload.get("password"):
            current["password_encrypted"] = self._cipher.encrypt_dict({"p": payload["password"]})
            current.pop("password", None)

        row.smtp_config = current
        self._db.flush()
        return self.get_smtp_public(tenant_id)
