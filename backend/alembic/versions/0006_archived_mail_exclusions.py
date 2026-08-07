"""Tombstones for permanently deleted archived mails (skip re-archive)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_archived_mail_exclusions"
down_revision = "0005_schedule_historical_backfill"
branch_labels = None
depends_on = None


def _bi() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "archived_mail_exclusions",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("account_id", _bi(), sa.ForeignKey("mail_accounts.id"), nullable=False, index=True),
        sa.Column("provider_message_id", sa.String(512), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=True, index=True),
        sa.Column("source_mail_id", sa.String(36), nullable=True),
        sa.Column("created_by", _bi(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "provider_message_id",
            name="uq_exclusion_provider_msg",
        ),
    )


def downgrade() -> None:
    op.drop_table("archived_mail_exclusions")
