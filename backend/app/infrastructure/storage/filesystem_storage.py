"""Filesystem storage for archived mail (EML + attachments + metadata.json)."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.interfaces.mail_provider import RawMessage

logger = logging.getLogger(__name__)


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
    attachments: list[StoredAttachment]


class FilesystemMailStorage:
    def __init__(self, storage_root: str) -> None:
        self.root = Path(storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_message(
        self,
        *,
        tenant_id: int,
        account_id: int,
        mail_id: str,
        raw: RawMessage,
        extra_metadata: dict[str, Any] | None = None,
    ) -> StoredMail:
        now = datetime.now(UTC)
        rel_dir = Path(str(tenant_id)) / str(account_id) / f"{now.year:04d}" / f"{now.month:02d}" / mail_id
        abs_dir = self.root / rel_dir
        att_dir = abs_dir / "adjuntos"
        att_dir.mkdir(parents=True, exist_ok=True)

        eml_path = abs_dir / "mail.eml"
        eml_path.write_bytes(raw.eml_bytes)
        content_sha256 = hashlib.sha256(raw.eml_bytes).hexdigest()

        stored_attachments: list[StoredAttachment] = []
        for att in raw.attachments:
            safe_name = self._safe_filename(att.filename)
            att_path = att_dir / safe_name
            att_path.write_bytes(att.content)
            sha = hashlib.sha256(att.content).hexdigest()
            rel_att = str(rel_dir / "adjuntos" / safe_name)
            stored_attachments.append(
                StoredAttachment(
                    filename=att.filename,
                    content_type=att.content_type,
                    size_bytes=att.size_bytes,
                    sha256=sha,
                    relative_path=rel_att,
                )
            )

        metadata = {
            "mail_id": mail_id,
            "provider_message_id": raw.provider_message_id,
            "subject": raw.subject,
            "from": raw.from_address,
            "to": raw.to_addresses,
            "cc": raw.cc_addresses,
            "sent_at": raw.sent_at.isoformat() if raw.sent_at else None,
            "received_at": raw.received_at.isoformat() if raw.received_at else None,
            "folder": raw.folder,
            "has_attachments": raw.has_attachments,
            "size_bytes": raw.size_bytes,
            "content_sha256": content_sha256,
            "attachments": [
                {
                    "filename": a.filename,
                    "content_type": a.content_type,
                    "size_bytes": a.size_bytes,
                    "sha256": a.sha256,
                    "path": a.relative_path,
                }
                for a in stored_attachments
            ],
            "archived_at": now.isoformat(),
            **(extra_metadata or {}),
        }
        metadata_path = abs_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Stored mail id=%s path=%s sha=%s", mail_id, rel_dir, content_sha256[:12])
        return StoredMail(
            relative_dir=str(rel_dir),
            eml_path=str(rel_dir / "mail.eml"),
            metadata_path=str(rel_dir / "metadata.json"),
            content_sha256=content_sha256,
            attachments=stored_attachments,
        )

    def read_eml(self, relative_eml_path: str) -> bytes:
        return (self.root / relative_eml_path).read_bytes()

    def read_eml_from_dir(self, relative_dir: str) -> bytes:
        path = self.root / relative_dir / "mail.eml"
        if not path.is_file():
            raise FileNotFoundError(f"EML no encontrado: {relative_dir}/mail.eml")
        return path.read_bytes()

    def eml_absolute_path(self, relative_dir: str) -> Path:
        return self.root / relative_dir / "mail.eml"

    def read_attachment(self, relative_path: str) -> bytes:
        return (self.root / relative_path).read_bytes()

    def delete_mail_dir(self, relative_dir: str) -> None:
        import shutil

        path = self.root / relative_dir
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Deleted storage dir %s", relative_dir)

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in (name or "attachment"))
        return cleaned.strip()[:180] or "attachment"
