"""Add mail archive tables: accounts, archived_mails, attachments, archive_jobs.

Depends on ``0001_phase0``. Same ``_bi()`` helper as phase 0 for SQLite PKs.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_mail_archive"
down_revision = "0001_phase0"
branch_labels = None
depends_on = None


def _bi():
    """BIGINT on MySQL/MariaDB; INTEGER on SQLite for working AUTOINCREMENT."""
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "mail_accounts",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", _bi(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "email",
            "provider",
            name="uq_mail_accounts_owner_email_provider",
        ),
    )
    op.create_index("ix_mail_accounts_tenant_id", "mail_accounts", ["tenant_id"])
    op.create_index("ix_mail_accounts_user_id", "mail_accounts", ["user_id"])

    op.create_table(
        "archived_mails",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("account_id", _bi(), sa.ForeignKey("mail_accounts.id"), nullable=False),
        sa.Column("user_id", _bi(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_message_id", sa.String(length=512), nullable=False),
        sa.Column("folder_path", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("to_addresses", sa.Text(), nullable=True),
        sa.Column("cc_addresses", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), nullable=False),
        sa.Column("size_bytes", _bi(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("body_preview", sa.String(length=500), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("attachment_names", sa.Text(), nullable=True),
        sa.Column("deleted_from_provider", sa.Boolean(), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "provider_message_id",
            name="uq_archived_provider_msg",
        ),
    )
    op.create_index("ix_archived_mails_tenant_id", "archived_mails", ["tenant_id"])
    op.create_index("ix_archived_mails_account_id", "archived_mails", ["account_id"])
    op.create_index("ix_archived_mails_user_id", "archived_mails", ["user_id"])
    op.create_index("ix_archived_mails_content_sha256", "archived_mails", ["content_sha256"])

    op.create_table(
        "attachments",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("archived_mail_id", sa.String(length=36), sa.ForeignKey("archived_mails.id"), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", _bi(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
    )
    op.create_index("ix_attachments_tenant_id", "attachments", ["tenant_id"])
    op.create_index("ix_attachments_archived_mail_id", "attachments", ["archived_mail_id"])

    op.create_table(
        "archive_jobs",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", _bi(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", _bi(), sa.ForeignKey("mail_accounts.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("delete_after_archive", sa.Boolean(), nullable=False),
        sa.Column("total_messages", sa.Integer(), nullable=False),
        sa.Column("processed_messages", sa.Integer(), nullable=False),
        sa.Column("archived_messages", sa.Integer(), nullable=False),
        sa.Column("skipped_messages", sa.Integer(), nullable=False),
        sa.Column("failed_messages", sa.Integer(), nullable=False),
        sa.Column("total_bytes", _bi(), nullable=False),
        sa.Column("archived_bytes", _bi(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_archive_jobs_tenant_id", "archive_jobs", ["tenant_id"])
    op.create_index("ix_archive_jobs_user_id", "archive_jobs", ["user_id"])
    op.create_index("ix_archive_jobs_account_id", "archive_jobs", ["account_id"])
    op.create_index("ix_archive_jobs_status", "archive_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("archive_jobs")
    op.drop_table("attachments")
    op.drop_table("archived_mails")
    op.drop_table("mail_accounts")
