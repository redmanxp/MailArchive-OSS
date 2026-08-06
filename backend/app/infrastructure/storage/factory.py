"""Build MailStorage from settings (filesystem default, S3-compatible optional)."""

from __future__ import annotations

import logging

from app.config import Settings
from app.domain.interfaces.mail_storage import MailStorage
from app.infrastructure.storage.filesystem_storage import FilesystemMailStorage
from app.infrastructure.storage.s3_storage import S3MailStorage

logger = logging.getLogger(__name__)


def build_mail_storage(settings: Settings) -> MailStorage:
    backend = (settings.storage_backend or "filesystem").strip().lower()
    if backend in ("s3", "minio", "object"):
        logger.info(
            "Mail storage backend=s3 bucket=%s endpoint=%s",
            settings.s3_bucket,
            settings.s3_endpoint_url or "(aws)",
        )
        return S3MailStorage(
            bucket=settings.s3_bucket,
            region=settings.s3_region or "us-east-1",
            endpoint_url=settings.s3_endpoint_url or None,
            access_key=settings.s3_access_key or None,
            secret_key=settings.s3_secret_key or None,
            force_path_style=bool(settings.s3_force_path_style),
            prefix=settings.s3_prefix or "",
        )
    return FilesystemMailStorage(settings.storage_root)
