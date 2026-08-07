"""Add historical backfill flags to archive schedules."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_schedule_historical_backfill"
down_revision = "0004_archive_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "archive_schedules",
        sa.Column(
            "historical_backfill",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "archive_schedules",
        sa.Column("backfill_watermark_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("archive_schedules", "backfill_watermark_at")
    op.drop_column("archive_schedules", "historical_backfill")
