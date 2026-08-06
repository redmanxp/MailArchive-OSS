"""S3-compatible object storage for archived mail (AWS S3, MinIO, R2, Wasabi)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError

from app.domain.interfaces.mail_provider import RawMessage
from app.domain.interfaces.mail_storage import MailStorage, StoredAttachment, StoredMail

logger = logging.getLogger(__name__)


class S3MailStorage(MailStorage):
    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        force_path_style: bool = True,
        prefix: str = "",
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip().strip("/")
        cfg = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if (force_path_style and endpoint_url) else "auto"},
        )
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region or "us-east-1",
            "config": cfg,
        }
        if endpoint_url:
            # Trailing/leading whitespace breaks botocore URI validation.
            kwargs["endpoint_url"] = endpoint_url.strip().rstrip("/")
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key.strip()
            kwargs["aws_secret_access_key"] = secret_key.strip()
        self._client: BaseClient = boto3.client(**kwargs)

    def _key(self, relative: str) -> str:
        rel = relative.replace("\\", "/").lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{rel}"
        return rel

    def health_check(self) -> tuple[bool, str]:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True, f"s3://{self.bucket}"
        except ClientError as exc:
            code = str((exc.response or {}).get("Error", {}).get("Code", ""))
            if code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    self._client.create_bucket(Bucket=self.bucket)
                    return True, f"s3://{self.bucket} (created)"
                except Exception as create_exc:
                    return False, str(create_exc)
            return False, str(exc)
        except Exception as exc:
            return False, str(exc)

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
        rel_dir = f"{tenant_id}/{account_id}/{now.year:04d}/{now.month:02d}/{mail_id}"
        content_sha256 = hashlib.sha256(raw.eml_bytes).hexdigest()

        self._put_bytes(f"{rel_dir}/mail.eml", raw.eml_bytes, "message/rfc822")

        stored_attachments: list[StoredAttachment] = []
        for att in raw.attachments:
            safe_name = self._safe_filename(att.filename)
            rel_att = f"{rel_dir}/adjuntos/{safe_name}"
            self._put_bytes(rel_att, att.content, att.content_type or "application/octet-stream")
            sha = hashlib.sha256(att.content).hexdigest()
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
        meta_bytes = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
        self._put_bytes(f"{rel_dir}/metadata.json", meta_bytes, "application/json")
        logger.info("Stored mail (S3) id=%s path=%s sha=%s", mail_id, rel_dir, content_sha256[:12])
        return StoredMail(
            relative_dir=rel_dir,
            eml_path=f"{rel_dir}/mail.eml",
            metadata_path=f"{rel_dir}/metadata.json",
            content_sha256=content_sha256,
            attachments=stored_attachments,
        )

    def read_eml_from_dir(self, relative_dir: str) -> bytes:
        key = f"{relative_dir.rstrip('/')}/mail.eml"
        try:
            return self._get_bytes(key)
        except ClientError as exc:
            if str((exc.response or {}).get("Error", {}).get("Code", "")) in (
                "404",
                "NoSuchKey",
                "NotFound",
            ):
                raise FileNotFoundError(f"EML no encontrado: {key}") from exc
            raise

    def read_attachment(self, relative_path: str) -> bytes:
        try:
            return self._get_bytes(relative_path)
        except ClientError as exc:
            if str((exc.response or {}).get("Error", {}).get("Code", "")) in (
                "404",
                "NoSuchKey",
                "NotFound",
            ):
                raise FileNotFoundError(f"Adjunto no encontrado: {relative_path}") from exc
            raise

    def delete_mail_dir(self, relative_dir: str) -> None:
        prefix = self._key(relative_dir.rstrip("/") + "/")
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            to_delete: list[dict[str, str]] = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents") or []:
                    to_delete.append({"Key": obj["Key"]})
            for i in range(0, len(to_delete), 1000):
                chunk = to_delete[i : i + 1000]
                if chunk:
                    self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": chunk})
            logger.info("Deleted S3 prefix %s (%s objects)", prefix, len(to_delete))
        except Exception as exc:
            logger.warning("S3 delete_mail_dir failed for %s: %s", relative_dir, exc)

    def _put_bytes(self, relative: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=self._key(relative),
            Body=data,
            ContentType=content_type,
        )

    def _get_bytes(self, relative: str) -> bytes:
        resp = self._client.get_object(Bucket=self.bucket, Key=self._key(relative))
        return resp["Body"].read()

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in (name or "attachment"))
        return cleaned.strip()[:180] or "attachment"
