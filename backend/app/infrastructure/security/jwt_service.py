"""JWT token service."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import Settings
from app.domain.exceptions import AuthenticationError
from app.domain.interfaces.repositories import ITokenService


class JwtTokenService(ITokenService):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_access_token(self, claims: dict[str, Any]) -> str:
        payload = dict(claims)
        expire = datetime.now(UTC) + timedelta(minutes=self._settings.jwt_access_token_expire_minutes)
        payload.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def create_refresh_token(self, claims: dict[str, Any]) -> str:
        payload = dict(claims)
        expire = datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        payload.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except JWTError as exc:
            raise AuthenticationError("Token inválido o expirado") from exc

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
