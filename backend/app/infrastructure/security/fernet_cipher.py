"""Fernet encryption for OAuth tokens and IMAP passwords."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class CredentialCipher:
    def __init__(self, settings: Settings) -> None:
        key = settings.data_encryption_key.encode("utf-8")
        try:
            self._fernet = Fernet(key)
        except Exception as exc:
            raise ValueError(
                "DATA_ENCRYPTION_KEY inválida. Generar con Fernet.generate_key()"
            ) from exc

    def encrypt_dict(self, data: dict[str, Any]) -> str:
        payload = json.dumps(data).encode("utf-8")
        return self._fernet.encrypt(payload).decode("utf-8")

    def decrypt_dict(self, token: str) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(token.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("No se pudieron descifrar las credenciales") from exc
        return json.loads(raw.decode("utf-8"))
