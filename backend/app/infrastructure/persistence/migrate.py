"""Apply Alembic migrations when the API process starts.

Why run migrations here
-----------------------
Docker / one-command installs should not require a separate ``alembic upgrade``
step. We still keep ``create_all`` as a safety net in ``main.py`` for edge cases.

Legacy DBs created only with ``create_all`` have no ``alembic_version`` row.
In that case we *stamp* the matching revision(s) instead of re-running CREATE
TABLE (which would fail).
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger("mailarchive.migrate")

# .../backend/app/infrastructure/persistence/migrate.py → backend/
BACKEND_ROOT = Path(__file__).resolve().parents[3]


def run_migrations(engine: Engine) -> None:
    """Bring the database to Alembic ``head``.

    Stamp path (legacy create_all DBs):
      * core tables, no version table → stamp ``0001_phase0``
      * mail tables already present → stamp ``0002_mail_archive`` and return
    """
    alembic_ini = BACKEND_ROOT / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    has_version = "alembic_version" in tables
    has_core = "tenants" in tables and "users" in tables
    has_mail = "mail_accounts" in tables

    if has_core and not has_version:
        logger.warning(
            "DB has schema but no alembic_version; stamping 0001_phase0 before upgrade"
        )
        command.stamp(cfg, "0001_phase0")
        if has_mail:
            command.stamp(cfg, "0002_mail_archive")
            logger.info("Stamped alembic to 0002_mail_archive (tables already present)")
            # Fall through so later revisions (e.g. FTS) still apply.

    try:
        command.upgrade(cfg, "head")
        logger.info("Alembic migrations applied (head)")
    except Exception:
        logger.exception("Alembic upgrade failed")
        raise
