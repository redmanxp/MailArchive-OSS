"""IMAP MailProvider implementation."""

from __future__ import annotations

import email
import logging
from datetime import UTC, datetime, timedelta
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

    # UIDs are per-folder; encode folder in provider ids when scanning the whole mailbox.
    _ID_SEP = "\x1f"

    @classmethod
    def _compose_message_id(cls, folder: str, uid: int | str) -> str:
        return f"{folder}{cls._ID_SEP}{uid}"

    @classmethod
    def _parse_message_id(cls, message_id: str, folder: str | None = None) -> tuple[str, int]:
        if cls._ID_SEP in message_id:
            folder_part, uid_part = message_id.split(cls._ID_SEP, 1)
            return folder_part, int(uid_part)
        return (folder or "INBOX"), int(message_id)

    @classmethod
    def message_id_aliases(cls, message_id: str, folder: str | None = None) -> list[str]:
        """Lookup candidates for plain UID ↔ folder\\x1fuid (legacy vs multi-folder ids).

        Pre-composite IMAP only scanned INBOX and stored bare UIDs. Bare UID must only
        alias to INBOX (UIDs are per-folder — never match Sent UID against INBOX row).
        """
        if not message_id:
            return []
        ids: list[str] = []

        def _add(value: str) -> None:
            if value and value not in ids:
                ids.append(value)

        _add(message_id)
        if cls._ID_SEP in message_id:
            folder_part, uid_part = message_id.split(cls._ID_SEP, 1)
            _add(cls._compose_message_id(folder_part, uid_part))
            # Legacy bare UID only existed for INBOX scans.
            if folder_part.upper() == "INBOX":
                _add(uid_part)
        else:
            # Bare UID → only INBOX composite (legacy storage was INBOX-only).
            _add(cls._compose_message_id("INBOX", message_id))
        _ = folder  # API compat; bare UIDs never alias across folders
        return ids

    def list_messages(self, query: MessageQuery) -> list[MessageSummary]:
        client = self._require()
        # Empty folder_ids = all selectable folders (scheduled archive / full mailbox).
        folders = list(query.folder_ids) if query.folder_ids else [f.id for f in self.list_folders()]
        if not folders:
            folders = ["INBOX"]

        results: list[MessageSummary] = []

        # Targeted fetch by id (may include composite folder\x1fuid ids).
        if query.message_ids:
            for mid in query.message_ids[: query.limit]:
                try:
                    folder, uid = self._parse_message_id(mid, None)
                    client.select_folder(folder, readonly=True)
                    fetched = client.fetch([uid], ["ENVELOPE", "RFC822.SIZE", "BODYSTRUCTURE"])
                    results.extend(
                        self._summaries_from_fetch(fetched, folder=folder, query=query)
                    )
                except Exception:
                    logger.exception("IMAP fetch by id failed for %s", mid)
            return results[: query.limit]

        criteria: list
        if query.older_than:
            # IMAP BEFORE is date-only and exclusive of that calendar day. Use the next
            # day so same-day messages before the watermark are still candidates; then
            # filter client-side with the full timestamp.
            ot = query.older_than
            if ot.tzinfo is None:
                ot = ot.replace(tzinfo=UTC)
            else:
                ot = ot.astimezone(UTC)
            before_day = ot.date() + timedelta(days=1)
            criteria = ["BEFORE", before_day.strftime("%d-%b-%Y")]
        elif query.date_from or query.date_to:
            criteria = []
            if query.date_from:
                criteria.extend(["SINCE", query.date_from.strftime("%d-%b-%Y")])
            if query.date_to:
                criteria.extend(["BEFORE", query.date_to.strftime("%d-%b-%Y")])
            if not criteria:
                criteria = ["ALL"]
        else:
            criteria = ["ALL"]

        for folder in folders:
            try:
                client.select_folder(folder, readonly=True)
            except Exception:
                logger.warning("IMAP skip non-selectable folder %s", folder)
                continue
            try:
                uids = client.search(criteria)
            except Exception:
                logger.exception("IMAP search failed in %s", folder)
                continue
            if not uids:
                continue
            # Cap per folder, then merge/sort so one busy folder does not starve the rest.
            uids = uids[-query.limit :] if len(uids) > query.limit else uids
            fetched = client.fetch(uids, ["ENVELOPE", "RFC822.SIZE", "BODYSTRUCTURE"]) if uids else {}
            results.extend(self._summaries_from_fetch(fetched, folder=folder, query=query))

        results.sort(
            key=lambda m: m.received_at or m.sent_at or datetime.min,
            reverse=True,
        )
        return results[: query.limit]

    def _summaries_from_fetch(
        self,
        fetched: dict,
        *,
        folder: str,
        query: MessageQuery,
    ) -> list[MessageSummary]:
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
                from_addr = (
                    f"{mailbox.mailbox.decode()}@{mailbox.host.decode()}"
                    if mailbox.mailbox and mailbox.host
                    else ""
                )
            to_addrs: list[str] = []
            if env and env.to:
                for t in env.to:
                    if t.mailbox and t.host:
                        to_addrs.append(f"{t.mailbox.decode()}@{t.host.decode()}")
            has_att = self._has_attachments(data.get(b"BODYSTRUCTURE"))
            if query.only_with_attachments and not has_att:
                continue
            sent_at = env.date if env and isinstance(env.date, datetime) else None
            if query.older_than and sent_at is not None:
                ts = sent_at if sent_at.tzinfo is not None else sent_at.replace(tzinfo=UTC)
                ot = query.older_than
                ot = ot if ot.tzinfo is not None else ot.replace(tzinfo=UTC)
                if ts.astimezone(UTC) >= ot.astimezone(UTC):
                    continue
            results.append(
                MessageSummary(
                    id=self._compose_message_id(folder, uid),
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
        target, uid = self._parse_message_id(message_id, folder)
        client.select_folder(target, readonly=True)
        data = client.fetch([uid], ["RFC822"])
        raw_bytes = data[uid][b"RFC822"]
        return self._parse_eml(
            raw_bytes,
            provider_message_id=self._compose_message_id(target, uid),
            folder=target,
        )

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
        target, uid = self._parse_message_id(message_id, folder)
        client.select_folder(target, readonly=False)
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
