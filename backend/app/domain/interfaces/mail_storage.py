"""Mail blob storage port — EML + attachments + metadata (filesystem or object storage)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.domain.interfaces.mail_provider import RawMessage


@dataclass
class StoredAttachment:
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    relative_path: str


@dataclass
class StoredMail:
    relative_dir: str
    eml_path: str
    metadata_path: str
    content_sha256: str
    attachments: list[StoredAttachment] = field(default_factory=list)


class MailStorage(ABC):
    """Persist archived mail blobs. Paths are relative POSIX keys under the backend root/bucket."""

    @abstractmethod
    def save_message(
        self,
        *,
        tenant_id: int,
        account_id: int,
        mail_id: str,
        raw: RawMessage,
        extra_metadata: dict[str, Any] | None = None,
    ) -> StoredMail: ...

    @abstractmethod
    def read_eml_from_dir(self, relative_dir: str) -> bytes: ...

    @abstractmethod
    def read_attachment(self, relative_path: str) -> bytes: ...

    @abstractmethod
    def delete_mail_dir(self, relative_dir: str) -> None: ...

    def health_check(self) -> tuple[bool, str]:
        """Optional probe for dashboard. Default: OK."""
        return True, "ok"
