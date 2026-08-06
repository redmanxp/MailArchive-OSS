"""S3-compatible storage with moto."""

from __future__ import annotations

from datetime import UTC, datetime

import boto3
from moto import mock_aws

from app.domain.interfaces.mail_provider import RawAttachment, RawMessage
from app.infrastructure.storage.s3_storage import S3MailStorage


@mock_aws
def test_s3_save_read_delete() -> None:
    conn = boto3.client("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="mailarchive-test")

    storage = S3MailStorage(
        bucket="mailarchive-test",
        region="us-east-1",
        access_key="testing",
        secret_key="testing",
        force_path_style=False,
    )
    raw = RawMessage(
        provider_message_id="p1",
        eml_bytes=b"From: a@b.c\r\n\r\nHi",
        subject="Hi",
        from_address="a@b.c",
        to_addresses=["x@y.z"],
        cc_addresses=[],
        sent_at=datetime(2024, 6, 1, tzinfo=UTC),
        received_at=datetime(2024, 6, 1, tzinfo=UTC),
        has_attachments=True,
        size_bytes=20,
        body_text="Hi",
        body_preview="Hi",
        folder="INBOX",
        attachments=[
            RawAttachment(
                filename="a.txt",
                content_type="text/plain",
                size_bytes=3,
                content=b"abc",
            )
        ],
    )
    stored = storage.save_message(tenant_id=1, account_id=2, mail_id="uuid-1", raw=raw)
    assert storage.read_eml_from_dir(stored.relative_dir) == raw.eml_bytes
    assert storage.read_attachment(stored.attachments[0].relative_path) == b"abc"
    ok, detail = storage.health_check()
    assert ok is True
    assert "mailarchive-test" in detail
    storage.delete_mail_dir(stored.relative_dir)
    try:
        storage.read_eml_from_dir(stored.relative_dir)
        raise AssertionError("expected missing eml")
    except FileNotFoundError:
        pass
