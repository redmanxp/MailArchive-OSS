"""Content-addressed storage keys and RFC Message-ID identity helpers."""

from __future__ import annotations

import email
import hashlib
import re
from datetime import datetime

_MSGID_JUNK = {"", "nil", "none", "null", "<>"}


def cas_eml_key(tenant_id: int, sha256: str) -> str:
    return f"{tenant_id}/cas/eml/{sha256}"


def cas_att_key(tenant_id: int, sha256: str) -> str:
    return f"{tenant_id}/cas/att/{sha256}"


def is_cas_path(relative: str | None) -> bool:
    if not relative:
        return False
    parts = relative.replace("\\", "/").strip("/").split("/")
    return len(parts) >= 2 and parts[1] == "cas"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_rfc_message_id(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).strip().split())
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    text = text.lower()
    if text in _MSGID_JUNK:
        return None
    return text[:512]


def rfc_message_id_from_eml(eml_bytes: bytes) -> str | None:
    try:
        msg = email.message_from_bytes(eml_bytes)
    except Exception:
        return None
    raw = msg.get("Message-ID") or msg.get("Message-Id") or msg.get("Message-id")
    return normalize_rfc_message_id(raw)


def _norm_addr(value: str | None) -> str:
    return (value or "").strip().lower()


def _norm_subject(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def identity_matches(
    *,
    donor_from: str | None,
    donor_subject: str | None,
    donor_sent_at: datetime | None,
    from_address: str | None,
    subject: str | None,
    sent_at: datetime | None,
    max_sent_skew_seconds: int = 120,
) -> bool:
    """Guard against colliding/spoofed Message-IDs before sharing a blob."""
    if _norm_addr(donor_from) != _norm_addr(from_address):
        return False
    if _norm_subject(donor_subject) != _norm_subject(subject):
        return False
    if donor_sent_at is None or sent_at is None:
        return True
    a = donor_sent_at
    b = sent_at
    if a.tzinfo is None and b.tzinfo is not None:
        b = b.replace(tzinfo=None)
    elif b.tzinfo is None and a.tzinfo is not None:
        a = a.replace(tzinfo=None)
    return abs((a - b).total_seconds()) <= max_sent_skew_seconds
