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

    def put_blob_if_absent(self, relative: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """Write CAS blob if missing. Returns True if this call created the object."""
        raise NotImplementedError

    def put_blob_from_path(self, relative: str, source: str, content_type: str = "application/octet-stream") -> bool:
        from pathlib import Path

        return self.put_blob_if_absent(relative, Path(source).read_bytes(), content_type)

    def delete_blob(self, relative: str) -> None:
        """Delete a CAS blob. Missing keys are ignored."""
        raise NotImplementedError

    def write_mail_sidecar(
        self,
        *,
        tenant_id: int,
        account_id: int,
        mail_id: str,
        content_sha256: str,
        attachments: list[StoredAttachment],
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Write metadata.json for a mail that reuses existing CAS blobs. Returns relative_dir."""
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        """Optional probe for dashboard. Default: OK."""
        return True, "ok"
