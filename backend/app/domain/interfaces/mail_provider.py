"""MailProvider port — domain never depends on Graph/IMAP concrete APIs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectionResult:
    ok: bool
    detail: str = ""
    email: str | None = None


@dataclass
class Folder:
    id: str
    name: str
    path: str
    total_items: int | None = None


@dataclass
class MessageQuery:
    folder_ids: list[str] = field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    older_than: datetime | None = None
    min_size_bytes: int | None = None
    only_with_attachments: bool = False
    message_ids: list[str] = field(default_factory=list)
    limit: int = 100
    page_token: str | None = None


@dataclass
class MessageSummary:
    id: str
    subject: str
    from_address: str
    to_addresses: list[str]
    sent_at: datetime | None
    received_at: datetime | None
    size_bytes: int
    has_attachments: bool
    folder: str


@dataclass
class RawAttachment:
    filename: str
    content_type: str
    size_bytes: int
    content: bytes
    content_id: str | None = None


@dataclass
class RawMessage:
    provider_message_id: str
    eml_bytes: bytes
    subject: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    sent_at: datetime | None
    received_at: datetime | None
    has_attachments: bool
    size_bytes: int
    body_text: str
    body_preview: str
    folder: str
    attachments: list[RawAttachment] = field(default_factory=list)
    headers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchiveOptions:
    delete_after_archive: bool = False


@dataclass
class ArchiveResult:
    provider_message_id: str
    deleted_from_provider: bool = False


@dataclass
class RestoreResult:
    provider_message_id: str
    folder: str


class MailProvider(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def test_connection(self) -> ConnectionResult: ...

    @abstractmethod
    def list_folders(self) -> list[Folder]: ...

    @abstractmethod
    def list_messages(self, query: MessageQuery) -> list[MessageSummary]: ...

    @abstractmethod
    def download_message(self, message_id: str, folder: str | None = None) -> RawMessage: ...

    @abstractmethod
    def archive_message(self, message_id: str, options: ArchiveOptions) -> ArchiveResult: ...

    @abstractmethod
    def restore_message(self, raw_eml: bytes, folder: str | None = None) -> RestoreResult: ...

    @abstractmethod
    def delete_message(self, message_id: str, folder: str | None = None) -> None: ...
