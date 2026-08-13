"""S3-compatible object storage for archived mail (AWS S3, MinIO, R2, Wasabi)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError

from app.domain.interfaces.mail_provider import RawMessage
from app.domain.interfaces.mail_storage import MailStorage, StoredAttachment, StoredMail
from app.infrastructure.storage.cas import cas_att_key, cas_eml_key, is_cas_path, sha256_bytes

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

    def put_blob_if_absent(self, relative: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        if self._blob_exists(relative):
            return False
        self._put_bytes(relative, data, content_type)
        return True

    def delete_blob(self, relative: str) -> None:
        if not relative or not is_cas_path(relative):
            logger.warning("Refuse delete_blob on non-CAS path %s", relative)
            return
        try:
            self._client.delete_object(Bucket=self.bucket, Key=self._key(relative))
            logger.info("Deleted S3 CAS blob %s", relative)
        except Exception as exc:
            logger.warning("S3 delete_blob failed for %s: %s", relative, exc)

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
        rel_dir = f"{tenant_id}/{account_id}/{now.year:04d}/{now.month:02d}/{mail_id}"
        eml_cas = cas_eml_key(tenant_id, content_sha256)
        metadata = {
            "mail_id": mail_id,
            "content_sha256": content_sha256,
            "eml_cas_path": eml_cas,
            "cas": True,
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
        self._put_bytes(
            f"{rel_dir}/metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
        )
        return rel_dir

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
        if not self.put_blob_if_absent(eml_cas, raw.eml_bytes, "message/rfc822"):
            logger.info("S3 CAS reuse EML sha=%s mail_id=%s", content_sha256[:12], mail_id)

        stored_attachments: list[StoredAttachment] = []
        for att in raw.attachments:
            sha = sha256_bytes(att.content)
            rel_att = cas_att_key(tenant_id, sha)
            if not self.put_blob_if_absent(rel_att, att.content, att.content_type or "application/octet-stream"):
                logger.info("S3 CAS reuse att sha=%s name=%s", sha[:12], att.filename)
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
        logger.info("Stored mail (S3) id=%s path=%s sha=%s", mail_id, rel_dir, content_sha256[:12])
        return StoredMail(
            relative_dir=rel_dir,
            eml_path=eml_cas,
            metadata_path=f"{rel_dir}/metadata.json",
            content_sha256=content_sha256,
            attachments=stored_attachments,
        )

    def read_eml_from_dir(self, relative_dir: str) -> bytes:
        key = f"{relative_dir.rstrip('/')}/mail.eml"
        try:
            return self._get_bytes(key)
        except ClientError as exc:
            code = str((exc.response or {}).get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchKey", "NotFound"):
                raise
        try:
            meta = json.loads(self._get_bytes(f"{relative_dir.rstrip('/')}/metadata.json"))
        except ClientError as exc:
            raise FileNotFoundError(f"EML no encontrado: {key}") from exc
        cas = meta.get("eml_cas_path")
        if cas:
            try:
                return self._get_bytes(cas)
            except ClientError:
                pass
        sha = meta.get("content_sha256")
        if sha:
            tenant = relative_dir.replace("\\", "/").split("/")[0]
            try:
                return self._get_bytes(cas_eml_key(int(tenant), sha))
            except ClientError:
                pass
        raise FileNotFoundError(f"EML no encontrado: {key}")

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
        if is_cas_path(relative_dir):
            logger.warning("Refuse delete_mail_dir on CAS path %s", relative_dir)
            return
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

    def _blob_exists(self, relative: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key(relative))
            return True
        except ClientError as exc:
            code = str((exc.response or {}).get("Error", {}).get("Code", ""))
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

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
