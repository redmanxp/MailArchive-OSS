"""Microsoft Graph MailProvider + OAuth helpers."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart  # noqa: F401 — kept for potential draft helpers
from email.mime.text import MIMEText  # noqa: F401
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
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

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class MicrosoftOAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.settings.microsoft_tenant_id}"

    def build_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": self.settings.microsoft_redirect_uri,
            "response_mode": "query",
            "scope": self.settings.microsoft_scopes,
            "state": state,
            # Forzar elección/login: no reutilizar la sesión Microsoft de otro usuario en la misma PC.
            "prompt": "login",
        }
        return f"{self.authority}/oauth2/v2.0/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "client_id": self.settings.microsoft_client_id,
            "client_secret": self.settings.microsoft_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.microsoft_redirect_uri,
            "scope": self.settings.microsoft_scopes,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.authority}/oauth2/v2.0/token", data=data)
            resp.raise_for_status()
            return resp.json()

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "client_id": self.settings.microsoft_client_id,
            "client_secret": self.settings.microsoft_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": self.settings.microsoft_scopes,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.authority}/oauth2/v2.0/token", data=data)
            resp.raise_for_status()
            return resp.json()


class MicrosoftGraphProvider(MailProvider):
    def __init__(
        self,
        *,
        settings: Settings,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
        on_tokens_refreshed: Any | None = None,
    ) -> None:
        self.settings = settings
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.on_tokens_refreshed = on_tokens_refreshed
        self._client: httpx.Client | None = None
        self._oauth = MicrosoftOAuthService(settings)

    def connect(self) -> None:
        self._ensure_token()
        self._client = httpx.Client(
            base_url=GRAPH_BASE,
            timeout=60.0,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _require(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("Graph no conectado")
        return self._client

    def _ensure_token(self) -> None:
        if self.expires_at and datetime.now(UTC) < (self.expires_at - timedelta(minutes=2)):
            return
        if not self.refresh_token:
            return
        logger.info("Refreshing Microsoft Graph token")
        tokens = self._oauth.refresh_tokens(self.refresh_token)
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token", self.refresh_token)
        expires_in = int(tokens.get("expires_in", 3600))
        self.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        if self.on_tokens_refreshed:
            self.on_tokens_refreshed(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires_at": self.expires_at.isoformat(),
                }
            )

    def test_connection(self) -> ConnectionResult:
        try:
            self.connect()
            resp = self._require().get("/me")
            resp.raise_for_status()
            data = resp.json()
            email = data.get("mail") or data.get("userPrincipalName")
            return ConnectionResult(ok=True, detail="Microsoft Graph OK", email=email)
        except Exception as exc:
            logger.exception("Graph test_connection failed")
            return ConnectionResult(ok=False, detail=str(exc))
        finally:
            self.disconnect()

    def list_folders(self) -> list[Folder]:
        """List all mail folders including nested childFolders."""
        client = self._require()
        results: list[Folder] = []

        def _page(url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            next_url: str | None = url
            next_params = params
            while next_url:
                if next_url.startswith("http"):
                    resp = client.get(next_url)
                else:
                    resp = client.get(next_url, params=next_params)
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("value", []))
                next_url = data.get("@odata.nextLink")
                next_params = None
            return items

        def _walk(folder_id: str | None, parent_path: str, depth: int) -> None:
            if depth > 12:
                return
            if folder_id is None:
                items = _page(
                    "/me/mailFolders",
                    {"$top": 100, "$select": "id,displayName,totalItemCount,childFolderCount"},
                )
            else:
                items = _page(
                    f"/me/mailFolders/{folder_id}/childFolders",
                    {"$top": 100, "$select": "id,displayName,totalItemCount,childFolderCount"},
                )
            for item in items:
                name = item.get("displayName") or ""
                path = f"{parent_path}/{name}" if parent_path else name
                results.append(
                    Folder(
                        id=item["id"],
                        name=name,
                        path=path,
                        total_items=item.get("totalItemCount"),
                    )
                )
                child_count = int(item.get("childFolderCount") or 0)
                if child_count > 0:
                    _walk(item["id"], path, depth + 1)

        _walk(None, "", 0)
        # Prefer human path order
        results.sort(key=lambda f: f.path.lower())
        return results

    def list_messages(self, query: MessageQuery) -> list[MessageSummary]:
        client = self._require()
        folder = query.folder_ids[0] if query.folder_ids else None
        path = f"/me/mailFolders/{folder}/messages" if folder else "/me/messages"
        select = "id,subject,from,toRecipients,receivedDateTime,sentDateTime,hasAttachments,bodyPreview"
        # PR_MESSAGE_SIZE (0x0E08): Graph no expone size en $select estándar.
        expand = "singleValueExtendedProperties($filter=id eq 'Integer 0x0E08')"
        params: dict[str, Any] = {
            "$top": min(max(query.limit, 1), 100),
            "$select": select,
            "$orderby": "receivedDateTime desc",
            "$expand": expand,
        }
        filters = []
        if query.older_than:
            filters.append(f"receivedDateTime lt {query.older_than.astimezone(UTC).isoformat()}")
        if query.date_from:
            filters.append(f"receivedDateTime ge {query.date_from.astimezone(UTC).isoformat()}")
        if query.date_to:
            filters.append(f"receivedDateTime le {query.date_to.astimezone(UTC).isoformat()}")
        if query.only_with_attachments:
            filters.append("hasAttachments eq true")
        if filters:
            params["$filter"] = " and ".join(filters)
        if query.message_ids:
            results = []
            for mid in query.message_ids[: query.limit]:
                r = client.get(
                    f"/me/messages/{mid}",
                    params={"$select": select, "$expand": expand},
                )
                if r.status_code == 200:
                    results.append(self._to_summary(r.json(), folder or "Inbox"))
            return results

        results: list[MessageSummary] = []
        next_url: str | None = path
        next_params: dict[str, Any] | None = params
        expand_disabled = False
        while next_url and len(results) < query.limit:
            if next_url.startswith("http"):
                resp = client.get(next_url)
            else:
                resp = client.get(next_url, params=next_params)
            if resp.status_code >= 400 and not expand_disabled and next_params and "$expand" in next_params:
                logger.warning("Graph list_messages expand size failed (%s); retry without size", resp.status_code)
                next_params = {k: v for k, v in next_params.items() if k != "$expand"}
                expand_disabled = True
                continue
            resp.raise_for_status()
            data = resp.json()
            for m in data.get("value", []):
                summary = self._to_summary(m, folder or "Inbox")
                if query.min_size_bytes is not None and summary.size_bytes < query.min_size_bytes:
                    continue
                results.append(summary)
                if len(results) >= query.limit:
                    break
            next_url = data.get("@odata.nextLink")
            next_params = None
        return results[: query.limit]

    def download_message(self, message_id: str, folder: str | None = None) -> RawMessage:
        client = self._require()
        meta = client.get(
            f"/me/messages/{message_id}",
            params={
                "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,hasAttachments,body,bodyPreview,parentFolderId"
            },
        )
        meta.raise_for_status()
        data = meta.json()

        # MIME content
        mime = client.get(f"/me/messages/{message_id}/$value")
        mime.raise_for_status()
        eml_bytes = mime.content

        attachments: list[RawAttachment] = []
        # Siempre consultar adjuntos: hasAttachments a veces es false con adjuntos reales.
        att_resp = client.get(f"/me/messages/{message_id}/attachments")
        if att_resp.status_code == 200:
            for att in att_resp.json().get("value", []):
                if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                    continue
                content_b64 = att.get("contentBytes") or ""
                content = base64.b64decode(content_b64) if content_b64 else b""
                attachments.append(
                    RawAttachment(
                        filename=att.get("name") or "attachment",
                        content_type=att.get("contentType") or "application/octet-stream",
                        size_bytes=int(att.get("size") or len(content)),
                        content=content,
                        content_id=att.get("contentId"),
                    )
                )
        elif att_resp.status_code not in (404,):
            logger.warning("Graph attachments list failed %s: %s", att_resp.status_code, att_resp.text[:200])

        from_address = ""
        if data.get("from") and data["from"].get("emailAddress"):
            from_address = data["from"]["emailAddress"].get("address", "")
        to_addresses = [
            x.get("emailAddress", {}).get("address", "")
            for x in data.get("toRecipients") or []
            if x.get("emailAddress")
        ]
        cc_addresses = [
            x.get("emailAddress", {}).get("address", "")
            for x in data.get("ccRecipients") or []
            if x.get("emailAddress")
        ]
        from app.infrastructure.storage.eml_utils import extract_bodies_from_eml, html_to_text

        body = data.get("body") or {}
        content_type = (body.get("contentType") or "").lower()
        content = body.get("content") or ""
        plain_eml, html_eml, preview_eml = extract_bodies_from_eml(eml_bytes)

        body_html = html_eml or (content if content_type == "html" else "")
        body_text = plain_eml or (content if content_type == "text" else "") or html_to_text(body_html) or (
            data.get("bodyPreview") or ""
        )
        # Persist plain for search; HTML is recovered from EML on detail view
        stored_body = body_text or body_html

        folder_label = self._resolve_folder_label(folder or data.get("parentFolderId"))

        sent_at = self._parse_dt(data.get("sentDateTime"))
        received_at = self._parse_dt(data.get("receivedDateTime"))
        return RawMessage(
            provider_message_id=data["id"],
            eml_bytes=eml_bytes,
            subject=data.get("subject") or "",
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            sent_at=sent_at,
            received_at=received_at,
            has_attachments=bool(attachments) or bool(data.get("hasAttachments")),
            size_bytes=len(eml_bytes),
            body_text=stored_body,
            body_preview=(data.get("bodyPreview") or preview_eml or body_text or "")[:500],
            folder=folder_label,
            attachments=attachments,
            headers={},
        )

    def _resolve_folder_label(self, folder_id: str | None) -> str:
        from app.infrastructure.storage.eml_utils import looks_like_graph_folder_id

        if not folder_id:
            return "Inbox"
        if not looks_like_graph_folder_id(folder_id):
            return folder_id
        client = self._require()
        parts: list[str] = []
        current: str | None = folder_id
        seen: set[str] = set()
        for _ in range(12):
            if not current or current in seen:
                break
            seen.add(current)
            try:
                resp = client.get(
                    f"/me/mailFolders/{current}",
                    params={"$select": "id,displayName,parentFolderId"},
                    timeout=20.0,
                )
                if resp.status_code >= 400:
                    break
                data = resp.json()
                name = data.get("displayName") or ""
                if name:
                    parts.append(name)
                parent = data.get("parentFolderId")
                # Root parent is often msgfolderroot — stop
                if not parent or parent == current:
                    break
                current = parent
            except Exception:
                break
        if not parts:
            return "Inbox"
        parts.reverse()
        # Drop generic root labels if present
        cleaned = [p for p in parts if p.lower() not in ("root", "top of information store")]
        return " / ".join(cleaned or parts)

    def archive_message(self, message_id: str, options: ArchiveOptions) -> ArchiveResult:
        self.download_message(message_id)
        deleted = False
        if options.delete_after_archive:
            self.delete_message(message_id)
            deleted = True
        return ArchiveResult(provider_message_id=message_id, deleted_from_provider=deleted)

    def _ensure_mailarchive_folder(self) -> tuple[str, str]:
        """Return (folder_id, display_name) for MailArchive; create if missing."""
        client = self._require()
        name = "MailArchive"

        def _find(items: list[dict[str, Any]]) -> str | None:
            for item in items:
                if (item.get("displayName") or "").strip().lower() == name.lower():
                    return item["id"]
            return None

        # Top-level
        top = client.get("/me/mailFolders", params={"$top": 200, "$select": "id,displayName,childFolderCount"})
        top.raise_for_status()
        top_items = top.json().get("value", [])
        found = _find(top_items)
        if found:
            return found, name

        # Under Inbox (where we create it)
        under_inbox = client.get(
            "/me/mailFolders/inbox/childFolders",
            params={"$top": 200, "$select": "id,displayName"},
        )
        if under_inbox.status_code < 400:
            found = _find(under_inbox.json().get("value", []))
            if found:
                return found, name

        create = client.post(
            "/me/mailFolders/inbox/childFolders",
            json={"displayName": name, "isHidden": False},
            timeout=30.0,
        )
        if create.status_code >= 400:
            create = client.post("/me/mailFolders", json={"displayName": name, "isHidden": False}, timeout=30.0)
        create.raise_for_status()
        data = create.json()
        logger.info("Created Graph folder MailArchive id=%s", data.get("id"))
        return data["id"], name

    def restore_message(self, raw_eml: bytes, folder: str | None = None) -> RestoreResult:
        """Restore into MailArchive (or explicit folder id). Never leave error-text drafts."""
        client = self._require()
        if folder:
            folder_id, folder_name = folder, folder
        else:
            folder_id, folder_name = self._ensure_mailarchive_folder()

        # 1) Prefer MIME import into target folder
        mime_error = ""
        try:
            resp = client.post(
                f"/me/mailFolders/{folder_id}/messages",
                content=raw_eml,
                headers={
                    "Content-Type": "text/plain",
                    "Content-Length": str(len(raw_eml)),
                },
                timeout=90.0,
            )
            if resp.status_code < 400:
                mid = resp.json().get("id", "")
                logger.info("Graph MIME restore OK folder=%s id=%s", folder_name, mid)
                return RestoreResult(provider_message_id=mid, folder=folder_name)
            mime_error = f"{resp.status_code} {resp.text[:300]}"
            logger.warning("Graph MIME restore rejected: %s", mime_error)
        except Exception as exc:
            mime_error = str(exc)
            logger.warning("Graph MIME restore exception: %s", mime_error)

        # 2) Structured create from EML parse (reliable path)
        try:
            mid = self._restore_from_parsed_eml(raw_eml, folder_id)
            logger.info("Graph structured restore OK folder=%s id=%s (mime failed: %s)", folder_name, mid, mime_error)
            return RestoreResult(provider_message_id=mid, folder=folder_name)
        except Exception as exc:
            logger.exception("Graph structured restore failed")
            raise RuntimeError(
                f"No se pudo restaurar a MailArchive. MIME: {mime_error or 'n/d'}; JSON: {exc}"
            ) from exc

    def _restore_from_parsed_eml(self, raw_eml: bytes, folder_id: str) -> str:
        import email as email_lib
        from email.header import decode_header, make_header
        from email.utils import getaddresses

        def _dec(value: str | None) -> str:
            if not value:
                return ""
            try:
                return str(make_header(decode_header(value)))
            except Exception:
                return value

        msg = email_lib.message_from_bytes(raw_eml)
        subject = _dec(msg.get("Subject")) or "(sin asunto)"
        to_addrs = [a for _, a in getaddresses(msg.get_all("To", []))]
        cc_addrs = [a for _, a in getaddresses(msg.get_all("Cc", []))]

        text_body = ""
        html_body = ""
        file_attachments: list[tuple[str, str, bytes]] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                payload = part.get_payload(decode=True) or b""
                if "attachment" in disp.lower() or part.get_filename():
                    fname = _dec(part.get_filename()) or "attachment"
                    file_attachments.append((fname, ctype or "application/octet-stream", payload))
                elif ctype == "text/plain" and not text_body:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
                elif ctype == "text/html" and not html_body:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            if msg.get_content_type() == "text/html":
                html_body = payload.decode(charset, errors="replace")
            else:
                text_body = payload.decode(charset, errors="replace")

        if html_body:
            body = {"contentType": "HTML", "content": html_body}
        else:
            body = {"contentType": "Text", "content": text_body or "(sin cuerpo)"}

        payload_json: dict[str, Any] = {
            "subject": subject,
            "body": body,
            "toRecipients": [{"emailAddress": {"address": a}} for a in to_addrs if a],
            "ccRecipients": [{"emailAddress": {"address": a}} for a in cc_addrs if a],
        }
        client = self._require()
        resp = client.post(f"/me/mailFolders/{folder_id}/messages", json=payload_json, timeout=60.0)
        resp.raise_for_status()
        mid = resp.json()["id"]

        for fname, ctype, content in file_attachments[:20]:
            if not content:
                continue
            att_payload = {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": fname[:200],
                "contentType": ctype,
                "contentBytes": base64.b64encode(content).decode("ascii"),
            }
            att_resp = client.post(f"/me/messages/{mid}/attachments", json=att_payload, timeout=60.0)
            if att_resp.status_code >= 400:
                logger.warning("No se pudo adjuntar %s: %s", fname, att_resp.text[:200])

        return mid

    def delete_message(self, message_id: str, folder: str | None = None) -> None:
        client = self._require()
        resp = client.delete(f"/me/messages/{message_id}")
        if resp.status_code not in (204, 404):
            resp.raise_for_status()

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _message_size_bytes(data: dict[str, Any]) -> int:
        import re

        for prop in data.get("singleValueExtendedProperties") or []:
            prop_id = str(prop.get("id") or "")
            # Graph: "Integer 0xe08" / "Integer 0x0E08" → PR_MESSAGE_SIZE
            if re.search(r"0[xX]0*[eE]08\b", prop_id) or prop_id.rstrip().endswith("3592"):
                try:
                    return max(0, int(prop.get("value") or 0))
                except (TypeError, ValueError):
                    return 0
        for key in ("size", "sizeInBytes"):
            if data.get(key) is not None:
                try:
                    return max(0, int(data[key]))
                except (TypeError, ValueError):
                    pass
        return 0

    @staticmethod
    def _to_summary(data: dict[str, Any], folder: str) -> MessageSummary:
        from_address = ""
        if data.get("from") and data["from"].get("emailAddress"):
            from_address = data["from"]["emailAddress"].get("address", "")
        to_addresses = [
            x.get("emailAddress", {}).get("address", "")
            for x in data.get("toRecipients") or []
            if x.get("emailAddress")
        ]
        return MessageSummary(
            id=data["id"],
            subject=data.get("subject") or "",
            from_address=from_address,
            to_addresses=to_addresses,
            sent_at=MicrosoftGraphProvider._parse_dt(data.get("sentDateTime")),
            received_at=MicrosoftGraphProvider._parse_dt(data.get("receivedDateTime")),
            size_bytes=MicrosoftGraphProvider._message_size_bytes(data),
            has_attachments=bool(data.get("hasAttachments")),
            folder=folder,
        )
