"""CAS blobs + RFC Message-ID for cross-mailbox storage dedup."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_content_cas"
down_revision = "0006_archived_mail_exclusions"
branch_labels = None
depends_on = None


def _bi() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "archived_mails",
        sa.Column("rfc_message_id", sa.String(512), nullable=True),
    )
    op.create_index("ix_archived_mails_rfc_message_id", "archived_mails", ["rfc_message_id"])

    op.create_table(
        "content_blobs",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("size_bytes", _bi(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("refcount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_content_blob_sha"),
    )


def downgrade() -> None:
    op.drop_table("content_blobs")
    op.drop_index("ix_archived_mails_rfc_message_id", table_name="archived_mails")
    op.drop_column("archived_mails", "rfc_message_id")
