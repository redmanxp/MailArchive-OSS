"""Run Alembic migrations programmatically at API startup."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger("mailarchive.migrate")

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def run_migrations(engine: Engine) -> None:
    """Apply Alembic migrations to head.

    If the DB was bootstrapped earlier with ``create_all`` (no alembic_version),
    stamp ``0001_phase0`` when core tables already exist so ``0002`` can apply.
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
            return

    try:
        command.upgrade(cfg, "head")
        logger.info("Alembic migrations applied (head)")
    except Exception:
        logger.exception("Alembic upgrade failed")
        raise
