"""IMAP MailProvider implementation."""

from __future__ import annotations

import email
import logging
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

from imapclient import IMAPClient

from app.domain.interfaces.mail_provider import (
    ArchiveOptions,
    ArchiveResult,
    ConnectionResult,
    Folder,
    MailProvider,
    MessageQuery,
    MessageSummary,
    RawAttachment,
    RawMessage,
    RestoreResult,
)

logger = logging.getLogger(__name__)


def _decode_mime(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


class ImapProvider(MailProvider):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        ssl: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssl = ssl
        self._client: IMAPClient | None = None

    def connect(self) -> None:
        logger.info("IMAP connect host=%s port=%s user=%s ssl=%s", self.host, self.port, self.username, self.ssl)
        self._client = IMAPClient(self.host, port=self.port, ssl=self.ssl, timeout=30)
        self._client.login(self.username, self.password)

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.logout()
            except Exception:
                pass
            self._client = None

    def _require(self) -> IMAPClient:
        if self._client is None:
            raise RuntimeError("IMAP no conectado")
        return self._client

    def test_connection(self) -> ConnectionResult:
        try:
            self.connect()
            self._require().noop()
            return ConnectionResult(ok=True, detail="Conexión IMAP OK", email=self.username)
        except Exception as exc:
            logger.exception("IMAP test_connection failed")
            return ConnectionResult(ok=False, detail=str(exc))
        finally:
            self.disconnect()

    def list_folders(self) -> list[Folder]:
        client = self._require()
        folders: list[Folder] = []
        for flags, delimiter, name in client.list_folders():
            folder_name = name.decode() if isinstance(name, bytes) else str(name)
            delim = delimiter.decode() if isinstance(delimiter, bytes) else (delimiter or "/")
            # Show nested structure using IMAP hierarchy delimiter
            display = folder_name.replace(delim, " / ") if delim else folder_name
            folders.append(
                Folder(
                    id=folder_name,
                    name=display,
                    path=display,
                    total_items=None,
                )
            )
        folders.sort(key=lambda f: f.path.lower())
        return folders

    def list_messages(self, query: MessageQuery) -> list[MessageSummary]:
        client = self._require()
        folder = query.folder_ids[0] if query.folder_ids else "INBOX"
        client.select_folder(folder, readonly=True)
        criteria: list = ["ALL"]
        if query.message_ids:
            # IMAP UIDs
            uids = [int(x) for x in query.message_ids]
            fetched = client.fetch(uids, ["ENVELOPE", "RFC822.SIZE", "BODYSTRUCTURE"])
        else:
            if query.older_than:
                criteria = ["BEFORE", query.older_than.strftime("%d-%b-%Y")]
            elif query.date_from or query.date_to:
                criteria = []
                if query.date_from:
                    criteria.extend(["SINCE", query.date_from.strftime("%d-%b-%Y")])
                if query.date_to:
                    criteria.extend(["BEFORE", query.date_to.strftime("%d-%b-%Y")])
                if not criteria:
                    criteria = ["ALL"]
            uids = client.search(criteria)
            uids = uids[: query.limit]
            fetched = client.fetch(uids, ["ENVELOPE", "RFC822.SIZE", "BODYSTRUCTURE"]) if uids else {}

        results: list[MessageSummary] = []
        for uid, data in fetched.items():
            env = data.get(b"ENVELOPE")
            size = int(data.get(b"RFC822.SIZE") or 0)
            if query.min_size_bytes and size < query.min_size_bytes:
                continue
            subject = _decode_mime(env.subject.decode() if env and env.subject else "")
            from_addr = ""
            if env and env.from_ and env.from_[0]:
                mailbox = env.from_[0]
                from_addr = f"{mailbox.mailbox.decode()}@{mailbox.host.decode()}" if mailbox.mailbox and mailbox.host else ""
            to_addrs: list[str] = []
            if env and env.to:
                for t in env.to:
                    if t.mailbox and t.host:
                        to_addrs.append(f"{t.mailbox.decode()}@{t.host.decode()}")
            has_att = self._has_attachments(data.get(b"BODYSTRUCTURE"))
            if query.only_with_attachments and not has_att:
                continue
            sent_at = env.date if env and isinstance(env.date, datetime) else None
            results.append(
                MessageSummary(
                    id=str(uid),
                    subject=subject,
                    from_address=from_addr,
                    to_addresses=to_addrs,
                    sent_at=sent_at,
                    received_at=sent_at,
                    size_bytes=size,
                    has_attachments=has_att,
                    folder=folder,
                )
            )
        return results

    def download_message(self, message_id: str, folder: str | None = None) -> RawMessage:
        client = self._require()
        target = folder or "INBOX"
        client.select_folder(target, readonly=True)
        uid = int(message_id)
        data = client.fetch([uid], ["RFC822"])
        raw_bytes = data[uid][b"RFC822"]
        return self._parse_eml(raw_bytes, provider_message_id=str(uid), folder=target)

    def archive_message(self, message_id: str, options: ArchiveOptions) -> ArchiveResult:
        raw = self.download_message(message_id)
        deleted = False
        if options.delete_after_archive:
            self.delete_message(message_id)
            deleted = True
        return ArchiveResult(provider_message_id=raw.provider_message_id, deleted_from_provider=deleted)

    def restore_message(self, raw_eml: bytes, folder: str | None = None) -> RestoreResult:
        client = self._require()
        target = folder or "MailArchive"
        # Ensure MailArchive (or target) exists
        existing = {name.decode() if isinstance(name, bytes) else str(name) for _, _, name in client.list_folders()}
        if target not in existing:
            try:
                client.create_folder(target)
                logger.info("Created IMAP folder %s", target)
            except Exception:
                logger.exception("No se pudo crear carpeta IMAP %s", target)
                # try with INBOX prefix
                alt = f"INBOX.{target}" if "INBOX" in existing else target
                if alt not in existing:
                    client.create_folder(alt)
                target = alt
        client.append(target, raw_eml)
        return RestoreResult(provider_message_id="", folder=target)

    def delete_message(self, message_id: str, folder: str | None = None) -> None:
        client = self._require()
        target = folder or "INBOX"
        client.select_folder(target, readonly=False)
        uid = int(message_id)
        client.delete_messages([uid])
        client.expunge()

    @staticmethod
    def _has_attachments(bodystructure) -> bool:
        if bodystructure is None:
            return False
        text = str(bodystructure).lower()
        return "attachment" in text or "application" in text

    @classmethod
    def _parse_eml(cls, raw_bytes: bytes, *, provider_message_id: str, folder: str) -> RawMessage:
        msg: Message = email.message_from_bytes(raw_bytes)
        subject = _decode_mime(msg.get("Subject"))
        from_address = _decode_mime(msg.get("From"))
        to_addresses = [_decode_mime(x) for x in (msg.get_all("To") or [])]
        cc_addresses = [_decode_mime(x) for x in (msg.get_all("Cc") or [])]
        sent_at = None
        try:
            if msg.get("Date"):
                sent_at = parsedate_to_datetime(msg.get("Date"))
        except Exception:
            sent_at = None

        body_text = ""
        html_body = ""
        attachments: list[RawAttachment] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if "attachment" in disp.lower() or (part.get_filename() and ctype not in ("text/plain", "text/html")):
                    payload = part.get_payload(decode=True) or b""
                    filename = part.get_filename() or "attachment"
                    attachments.append(
                        RawAttachment(
                            filename=_decode_mime(filename),
                            content_type=ctype,
                            size_bytes=len(payload),
                            content=payload,
                            content_id=part.get("Content-ID"),
                        )
                    )
                elif ctype == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
                elif ctype == "text/html" and not html_body:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_body = decoded
            else:
                body_text = decoded

        if not body_text and html_body:
            from app.infrastructure.storage.eml_utils import html_to_text

            body_text = html_to_text(html_body)

        preview = (body_text or html_body)[:500]
        return RawMessage(
            provider_message_id=provider_message_id,
            eml_bytes=raw_bytes,
            subject=subject,
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            sent_at=sent_at,
            received_at=sent_at,
            has_attachments=bool(attachments),
            size_bytes=len(raw_bytes),
            body_text=body_text or html_body,
            body_preview=preview,
            folder=folder,
            attachments=attachments,
        )
