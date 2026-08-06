"""Helpers to extract readable bodies from EML bytes."""

from __future__ import annotations

import email
import re
from email.header import decode_header, make_header
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3"):
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        text = "".join(self._chunks)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def looks_like_graph_folder_id(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("AAMk") or (len(value) > 60 and " " not in value and "/" not in value)


def extract_bodies_from_eml(raw_eml: bytes) -> tuple[str, str, str]:
    """Return (plain_text, html, preview). Prefer full content from MIME parts."""
    msg = email.message_from_bytes(raw_eml)
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and not plain:
                plain = decoded
            elif ctype == "text/html" and not html:
                html = decoded
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, errors="replace")
        if msg.get_content_type() == "text/html":
            html = decoded
        else:
            plain = decoded

    if not plain and html:
        plain = html_to_text(html)
    preview = (plain or html_to_text(html) if html else "")[:500]
    return plain, html, preview


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def extract_file_attachments_from_eml(raw_eml: bytes) -> list[tuple[str, str, bytes]]:
    """Return list of (filename, content_type, content) for attachment parts."""
    msg = email.message_from_bytes(raw_eml)
    results: list[tuple[str, str, bytes]] = []
    for part in msg.walk():
        disp = str(part.get("Content-Disposition") or "").lower()
        if "attachment" not in disp and not part.get_filename():
            continue
        if part.get_content_maintype() == "multipart":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        filename = decode_mime_header(part.get_filename()) or "adjunto"
        ctype = part.get_content_type() or "application/octet-stream"
        results.append((filename, ctype, payload))
    return results
