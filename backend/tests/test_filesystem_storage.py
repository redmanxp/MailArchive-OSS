"""EML + attachments + metadata.json layout on disk."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.domain.interfaces.mail_provider import RawAttachment, RawMessage
from app.infrastructure.storage.filesystem_storage import FilesystemMailStorage


def test_save_message_writes_eml_metadata_and_attachment(tmp_path: Path) -> None:
    storage = FilesystemMailStorage(str(tmp_path))
    eml = b"From: a@example.com\r\nSubject: Hello\r\n\r\nBody"
    att_bytes = b"file-bytes"
    raw = RawMessage(
        provider_message_id="prov-1",
        eml_bytes=eml,
        subject="Hello",
        from_address="a@example.com",
        to_addresses=["b@example.com"],
        cc_addresses=[],
        sent_at=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        received_at=datetime(2024, 1, 15, 12, 1, tzinfo=UTC),
        has_attachments=True,
        size_bytes=len(eml),
        body_text="Body",
        body_preview="Body",
        folder="INBOX",
        attachments=[
            RawAttachment(
                filename="note.txt",
                content_type="text/plain",
                size_bytes=len(att_bytes),
                content=att_bytes,
            )
        ],
    )

    stored = storage.save_message(
        tenant_id=1,
        account_id=2,
        mail_id="mail-uuid-1",
        raw=raw,
        extra_metadata={"job_id": 99},
    )

    assert stored.content_sha256 == hashlib.sha256(eml).hexdigest()
    eml_path = tmp_path / stored.eml_path
    assert eml_path.is_file()
    assert eml_path.read_bytes() == eml

    meta_path = tmp_path / stored.metadata_path
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["mail_id"] == "mail-uuid-1"
    assert meta["subject"] == "Hello"
    assert meta["job_id"] == 99
    assert meta["content_sha256"] == stored.content_sha256
    assert len(meta["attachments"]) == 1
    assert meta["attachments"][0]["filename"] == "note.txt"

    att_path = tmp_path / stored.attachments[0].relative_path
    assert att_path.read_bytes() == att_bytes
    assert storage.read_eml(stored.eml_path) == eml
    assert storage.read_eml_from_dir(stored.relative_dir) == eml
