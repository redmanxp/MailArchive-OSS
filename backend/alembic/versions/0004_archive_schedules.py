"""Per-account scheduled incremental archive policies."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_archive_schedules"
down_revision = "0003_mail_fts"
branch_labels = None
depends_on = None


def _bi() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "archive_schedules",
        sa.Column("id", _bi(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", _bi(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "account_id",
            _bi(),
            sa.ForeignKey("mail_accounts.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("folder_id", sa.String(512), nullable=True),
        sa.Column("folder_path", sa.String(512), nullable=True),
        sa.Column("limit_per_run", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("only_with_attachments", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("watermark_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("last_job_id", _bi(), nullable=True),
        sa.Column("last_status", sa.String(32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("archive_schedules")
