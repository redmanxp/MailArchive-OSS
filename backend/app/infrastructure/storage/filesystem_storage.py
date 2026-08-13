"""Filesystem storage for archived mail (CAS blobs + per-mail metadata.json)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.interfaces.mail_provider import RawMessage
from app.domain.interfaces.mail_storage import MailStorage, StoredAttachment, StoredMail
from app.infrastructure.storage.cas import cas_att_key, cas_eml_key, is_cas_path, sha256_bytes

logger = logging.getLogger(__name__)


class FilesystemMailStorage(MailStorage):
    def __init__(self, storage_root: str) -> None:
        self.root = Path(storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def health_check(self) -> tuple[bool, str]:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, str(self.root)
        except Exception as exc:
            return False, str(exc)

    def put_blob_from_path(self, relative: str, source: str, content_type: str = "application/octet-stream") -> bool:
        import os

        dest = self.root / relative
        if dest.is_file():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, dest)
            logger.debug("CAS hardlink %s -> %s", source, relative)
            return True
        except OSError:
            return self.put_blob_if_absent(relative, Path(source).read_bytes(), content_type)

    def put_blob_if_absent(self, relative: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        dest = self.root / relative
        if dest.is_file():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
        logger.debug("CAS put %s (%s bytes, %s)", relative, len(data), content_type)
        return True

    def delete_blob(self, relative: str) -> None:
        if not relative or not is_cas_path(relative):
            logger.warning("Refuse delete_blob on non-CAS path %s", relative)
            return
        path = self.root / relative
        if path.is_file():
            path.unlink()
            logger.info("Deleted CAS blob %s", relative)

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
        now = datetime.now(UTC)
        rel_dir = Path(str(tenant_id)) / str(account_id) / f"{now.year:04d}" / f"{now.month:02d}" / mail_id
        abs_dir = self.root / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        eml_cas = cas_eml_key(tenant_id, content_sha256)
        metadata = {
            "mail_id": mail_id,
            "content_sha256": content_sha256,
            "eml_cas_path": eml_cas,
            "cas": True,
            "size_bytes": extra_metadata.get("size_bytes") if extra_metadata else None,
            "attachments": [
                {
                    "filename": a.filename,
                    "content_type": a.content_type,
                    "size_bytes": a.size_bytes,
                    "sha256": a.sha256,
                    "path": a.relative_path,
                }
                for a in attachments
            ],
            "archived_at": now.isoformat(),
            **(extra_metadata or {}),
        }
        (abs_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(rel_dir)

    def save_message(
        self,
        *,
        tenant_id: int,
        account_id: int,
        mail_id: str,
        raw: RawMessage,
        extra_metadata: dict[str, Any] | None = None,
    ) -> StoredMail:
        content_sha256 = sha256_bytes(raw.eml_bytes)
        eml_cas = cas_eml_key(tenant_id, content_sha256)
        created = self.put_blob_if_absent(eml_cas, raw.eml_bytes, "message/rfc822")
        if not created:
            logger.info("CAS reuse EML sha=%s mail_id=%s", content_sha256[:12], mail_id)

        stored_attachments: list[StoredAttachment] = []
        for att in raw.attachments:
            sha = sha256_bytes(att.content)
            rel_att = cas_att_key(tenant_id, sha)
            att_created = self.put_blob_if_absent(
                rel_att, att.content, att.content_type or "application/octet-stream"
            )
            if not att_created:
                logger.info("CAS reuse att sha=%s name=%s", sha[:12], att.filename)
            stored_attachments.append(
                StoredAttachment(
                    filename=att.filename,
                    content_type=att.content_type,
                    size_bytes=att.size_bytes,
                    sha256=sha,
                    relative_path=rel_att,
                )
            )

        extra = {
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
            **(extra_metadata or {}),
        }
        rel_dir = self.write_mail_sidecar(
            tenant_id=tenant_id,
            account_id=account_id,
            mail_id=mail_id,
            content_sha256=content_sha256,
            attachments=stored_attachments,
            extra_metadata=extra,
        )
        logger.info("Stored mail id=%s path=%s sha=%s", mail_id, rel_dir, content_sha256[:12])
        return StoredMail(
            relative_dir=rel_dir,
            eml_path=eml_cas,
            metadata_path=f"{rel_dir}/metadata.json",
            content_sha256=content_sha256,
            attachments=stored_attachments,
        )

    def read_eml(self, relative_eml_path: str) -> bytes:
        return (self.root / relative_eml_path).read_bytes()

    def read_eml_from_dir(self, relative_dir: str) -> bytes:
        legacy = self.root / relative_dir / "mail.eml"
        if legacy.is_file():
            return legacy.read_bytes()
        meta_path = self.root / relative_dir / "metadata.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise FileNotFoundError(f"EML no encontrado: {relative_dir}/mail.eml") from exc
            cas = meta.get("eml_cas_path")
            if cas:
                cas_path = self.root / cas
                if cas_path.is_file():
                    return cas_path.read_bytes()
            sha = meta.get("content_sha256")
            if sha:
                tenant = relative_dir.replace("\\", "/").split("/")[0]
                cas_path = self.root / cas_eml_key(int(tenant), sha)
                if cas_path.is_file():
                    return cas_path.read_bytes()
        raise FileNotFoundError(f"EML no encontrado: {relative_dir}/mail.eml")

    def eml_absolute_path(self, relative_dir: str) -> Path:
        legacy = self.root / relative_dir / "mail.eml"
        if legacy.is_file():
            return legacy
        return self.root / relative_dir / "mail.eml"

    def read_attachment(self, relative_path: str) -> bytes:
        return (self.root / relative_path).read_bytes()

    def delete_mail_dir(self, relative_dir: str) -> None:
        import shutil

        if is_cas_path(relative_dir):
            logger.warning("Refuse delete_mail_dir on CAS path %s", relative_dir)
            return
        path = self.root / relative_dir
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Deleted storage dir %s", relative_dir)

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in (name or "attachment"))
        return cleaned.strip()[:180] or "attachment"
