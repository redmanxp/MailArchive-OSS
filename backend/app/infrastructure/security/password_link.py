"""Signed password-setup / password-reset links (no password in email)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt

from app.config import Settings
from app.domain.exceptions import AuthenticationError, ValidationError

Purpose = Literal["invite", "reset"]


class PasswordLinkService:
    def __init__(self, settings: Settings, *, ttl_hours: int = 48) -> None:
        self._settings = settings
        self._ttl_hours = ttl_hours

    def _pwd_fp(self, password_hash: str) -> str:
        return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:24]

    def issue(
        self,
        *,
        purpose: Purpose,
        tenant_id: int,
        user_id: int,
        email: str,
        name: str,
        password_hash: str,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "type": "password_link",
            "purpose": purpose,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email": email.lower(),
            "name": name,
            "pwd_fp": self._pwd_fp(password_hash),
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(hours=self._ttl_hours),
        }
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def verify(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except JWTError as exc:
            raise AuthenticationError("El enlace no es válido o expiró") from exc
        if payload.get("type") != "password_link":
            raise AuthenticationError("El enlace no es válido")
        if payload.get("purpose") not in ("invite", "reset"):
            raise AuthenticationError("El enlace no es válido")
        return payload

    def assert_still_valid(self, payload: dict[str, Any], password_hash: str) -> None:
        """Invalidate link once password changed (fingerprint mismatch)."""
        expected = self._pwd_fp(password_hash)
        if payload.get("pwd_fp") != expected:
            raise ValidationError("Este enlace ya fue usado o la contraseña cambió. Solicitá uno nuevo.")

    def build_url(self, token: str) -> str:
        base = (self._settings.app_url or "").rstrip("/")
        return f"{base}/set-password?token={token}"
