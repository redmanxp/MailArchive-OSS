"""Unit tests for FTS query helpers (no DB)."""

from app.infrastructure.persistence.fts import mysql_boolean_query, sanitize_fts_query


def test_sanitize_strips_operators() -> None:
    assert sanitize_fts_query("hola mundo!") == "hola mundo"
    assert sanitize_fts_query('invoice "2024" OR spam') == "invoice 2024 OR spam"


def test_sanitize_empty() -> None:
    assert sanitize_fts_query("") == ""
    assert sanitize_fts_query("+++") == ""


def test_mysql_boolean_prefix() -> None:
    q = mysql_boolean_query("invoice 2024")
    assert "+invoice*" in q
    assert "+2024*" in q
