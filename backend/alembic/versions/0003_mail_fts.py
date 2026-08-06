"""Native full-text search for archived mails.

SQLite: FTS5 virtual table ``archived_mails_fts`` (maintained by the repository).
MySQL/MariaDB: InnoDB FULLTEXT index on searchable columns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_mail_fts"
down_revision = "0002_mail_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute(
            sa.text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS archived_mails_fts USING fts5(
                    mail_id UNINDEXED,
                    tenant_id UNINDEXED,
                    subject,
                    from_address,
                    to_addresses,
                    cc_addresses,
                    body_preview,
                    body_text,
                    attachment_names,
                    tokenize = 'unicode61'
                )
                """
            )
        )
        op.execute(
            sa.text(
                """
                INSERT INTO archived_mails_fts(
                    mail_id, tenant_id, subject, from_address, to_addresses,
                    cc_addresses, body_preview, body_text, attachment_names
                )
                SELECT
                    id, CAST(tenant_id AS TEXT),
                    COALESCE(subject, ''),
                    COALESCE(from_address, ''),
                    COALESCE(to_addresses, ''),
                    COALESCE(cc_addresses, ''),
                    COALESCE(body_preview, ''),
                    COALESCE(body_text, ''),
                    COALESCE(attachment_names, '')
                FROM archived_mails
                """
            )
        )
        return

    # MySQL / MariaDB — FULLTEXT on InnoDB (requires compatible column types)
    op.execute(
        sa.text(
            """
            ALTER TABLE archived_mails
            ADD FULLTEXT INDEX ft_archived_mails_search (
                subject, from_address, to_addresses, cc_addresses,
                body_preview, body_text, attachment_names
            )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute(sa.text("DROP TABLE IF EXISTS archived_mails_fts"))
        return
    op.execute(sa.text("ALTER TABLE archived_mails DROP INDEX ft_archived_mails_search"))
