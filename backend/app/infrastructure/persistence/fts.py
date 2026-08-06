"""Full-text search helpers for archived mails (SQLite FTS5 / MySQL FULLTEXT)."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[\w@.\-]+", re.UNICODE)

# Columns indexed in both engines
_FTS_COLS = (
    "subject",
    "from_address",
    "to_addresses",
    "cc_addresses",
    "body_preview",
    "body_text",
    "attachment_names",
)


def dialect_name(db: Session) -> str:
    return db.get_bind().dialect.name


def sanitize_fts_query(q: str) -> str:
    """Build a safe FTS query from free text (tokens only, no operators)."""
    tokens = _TOKEN_RE.findall(q or "")
    return " ".join(tokens[:32])


def mysql_boolean_query(q: str) -> str:
    """MySQL BOOLEAN MODE: require each token as prefix match."""
    tokens = _TOKEN_RE.findall(q or "")
    parts = [f"+{t}*" for t in tokens[:32] if len(t) >= 2]
    return " ".join(parts)


def upsert_mail_fts(db: Session, row: Any) -> None:
    """Index or re-index one archived mail (SQLite FTS5 only; MySQL uses table FULLTEXT)."""
    if dialect_name(db) != "sqlite":
        return
    try:
        db.execute(
            text("DELETE FROM archived_mails_fts WHERE mail_id = :mail_id"),
            {"mail_id": row.id},
        )
        db.execute(
            text(
                """
                INSERT INTO archived_mails_fts(
                    mail_id, tenant_id, subject, from_address, to_addresses,
                    cc_addresses, body_preview, body_text, attachment_names
                ) VALUES (
                    :mail_id, :tenant_id, :subject, :from_address, :to_addresses,
                    :cc_addresses, :body_preview, :body_text, :attachment_names
                )
                """
            ),
            {
                "mail_id": row.id,
                "tenant_id": str(row.tenant_id),
                "subject": row.subject or "",
                "from_address": row.from_address or "",
                "to_addresses": row.to_addresses or "",
                "cc_addresses": row.cc_addresses or "",
                "body_preview": row.body_preview or "",
                "body_text": row.body_text or "",
                "attachment_names": row.attachment_names or "",
            },
        )
    except Exception:
        logger.exception("FTS upsert failed mail_id=%s", getattr(row, "id", None))


def delete_mail_fts(db: Session, mail_id: str) -> None:
    if dialect_name(db) != "sqlite":
        return
    try:
        db.execute(
            text("DELETE FROM archived_mails_fts WHERE mail_id = :mail_id"),
            {"mail_id": mail_id},
        )
    except Exception:
        logger.exception("FTS delete failed mail_id=%s", mail_id)


def fts_mail_ids(db: Session, tenant_id: int, q: str, *, limit: int = 5000) -> list[str] | None:
    """Return matching mail IDs via native FTS, or None to fall back to ILIKE."""
    cleaned = sanitize_fts_query(q)
    if not cleaned:
        return None
    dialect = dialect_name(db)
    try:
        if dialect == "sqlite":
            # Prefix each token for friendlier matching
            match_q = " ".join(f"{t}*" for t in cleaned.split())
            rows = db.execute(
                text(
                    """
                    SELECT mail_id FROM archived_mails_fts
                    WHERE archived_mails_fts MATCH :q AND tenant_id = :tenant_id
                    LIMIT :lim
                    """
                ),
                {"q": match_q, "tenant_id": str(tenant_id), "lim": limit},
            ).fetchall()
            return [str(r[0]) for r in rows]
        if dialect in ("mysql", "mariadb"):
            bool_q = mysql_boolean_query(q)
            if not bool_q:
                return None
            cols = ", ".join(_FTS_COLS)
            rows = db.execute(
                text(
                    f"""
                    SELECT id FROM archived_mails
                    WHERE tenant_id = :tenant_id
                      AND MATCH({cols}) AGAINST (:q IN BOOLEAN MODE)
                    LIMIT :lim
                    """
                ),
                {"tenant_id": tenant_id, "q": bool_q, "lim": limit},
            ).fetchall()
            return [str(r[0]) for r in rows]
    except Exception:
        logger.warning("Native FTS unavailable; falling back to ILIKE", exc_info=True)
        return None
    return None
