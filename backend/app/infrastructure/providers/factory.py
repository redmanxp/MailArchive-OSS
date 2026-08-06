"""MailProvider factory."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.config import Settings
from app.domain.enums.providers import MailProviderType
from app.domain.interfaces.mail_provider import MailProvider
from app.infrastructure.providers.imap_provider import ImapProvider
from app.infrastructure.providers.microsoft_graph import MicrosoftGraphProvider
from app.infrastructure.security.fernet_cipher import CredentialCipher


class MailProviderFactory:
    def __init__(self, settings: Settings, cipher: CredentialCipher) -> None:
        self.settings = settings
        self.cipher = cipher

    def create(
        self,
        *,
        provider: str,
        config: dict[str, Any] | None,
        credentials_encrypted: str | None,
        on_tokens_refreshed: Callable[[dict[str, Any]], None] | None = None,
    ) -> MailProvider:
        creds = self.cipher.decrypt_dict(credentials_encrypted) if credentials_encrypted else {}
        config = config or {}
        if provider == MailProviderType.IMAP.value:
            return ImapProvider(
                host=config.get("host") or creds.get("host", ""),
                port=int(config.get("port") or creds.get("port") or 993),
                username=creds.get("username") or config.get("username") or "",
                password=creds.get("password") or "",
                ssl=bool(config.get("ssl", True)),
            )
        if provider == MailProviderType.MICROSOFT365.value:
            expires_at = None
            if creds.get("expires_at"):
                expires_at = datetime.fromisoformat(creds["expires_at"])
            return MicrosoftGraphProvider(
                settings=self.settings,
                access_token=creds.get("access_token", ""),
                refresh_token=creds.get("refresh_token"),
                expires_at=expires_at,
                on_tokens_refreshed=on_tokens_refreshed,
            )
        if provider == MailProviderType.GMAIL.value:
            raise NotImplementedError("GmailProvider aún no implementado")
        raise ValueError(f"Proveedor no soportado: {provider}")
