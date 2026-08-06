"""SMTP notifier — send invite / password-reset messages via any SMTP relay.

Uses tenant ``smtp_config`` (host, credentials, from_*) and optional
``email_templates`` overrides (see ``templates.py``). Never logs passwords.
"""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.domain.interfaces.notifier import EmailResult, INotifier
from app.infrastructure.email.templates import merge_email_templates, render_template

logger = logging.getLogger(__name__)


def _cta_html(
    *,
    greeting: str,
    intro: str,
    button_label: str,
    url: str,
    footer: str,
    link_fallback: str,
    brand: str,
) -> str:
    """Minimal HTML email with a single CTA button (table layout for clients)."""
    safe_url = html.escape(url, quote=True)
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1a2b3c;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f6f8;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;background:#ffffff;border:1px solid #d5dee5;border-radius:8px;padding:28px 24px;">
          <tr><td style="font-size:20px;font-weight:700;color:#0B3D5C;padding-bottom:12px;">{html.escape(brand)}</td></tr>
          <tr><td style="font-size:15px;line-height:1.5;padding-bottom:8px;">{html.escape(greeting)}</td></tr>
          <tr><td style="font-size:15px;line-height:1.5;padding-bottom:22px;">{html.escape(intro)}</td></tr>
          <tr>
            <td align="center" style="padding-bottom:22px;">
              <a href="{safe_url}"
                 style="display:inline-block;background:#0B3D5C;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 28px;border-radius:6px;">
                {html.escape(button_label)}
              </a>
            </td>
          </tr>
          <tr><td style="font-size:13px;line-height:1.5;color:#5a6b7c;padding-bottom:8px;">{html.escape(footer)}</td></tr>
          <tr>
            <td style="font-size:12px;line-height:1.4;color:#8a9aab;word-break:break-all;">
              {html.escape(link_fallback)}<br/>
              <a href="{safe_url}" style="color:#0B3D5C;">{safe_url}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class SmtpNotifier(INotifier):
    """INotifier implementation backed by smtplib.

    ``smtp_config`` keys: host, port, user, password, from_email, from_name,
    starttls, enabled, email_templates (optional).
    """

    def __init__(self, smtp_config: dict | None) -> None:
        self._cfg = smtp_config or {}

    def _templates(self) -> dict:
        return merge_email_templates(self._cfg.get("email_templates"))

    def _brand(self) -> str:
        return str(self._cfg.get("from_name") or "MailArchive")

    def _send(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailResult:
        if not self._cfg:
            return EmailResult(ok=False, detail="SMTP no configurado")
        host = self._cfg.get("host", "")
        port = int(self._cfg.get("port", 587))
        user = self._cfg.get("user", "")
        password = self._cfg.get("password", "")
        from_email = self._cfg.get("from_email") or user
        from_name = self._cfg.get("from_name", "MailArchive")
        use_tls = bool(self._cfg.get("starttls", True))

        if not host or not user:
            return EmailResult(ok=False, detail="SMTP incompleto (host/user)")

        if body_html:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        else:
            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

        try:
            logger.info("Enviando email SMTP a=%s host=%s html=%s", to_email, host, bool(body_html))
            # Port 465 → implicit TLS; otherwise STARTTLS when enabled (typical 587).
            if use_tls and port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
                    server.login(user, password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=30) as server:
                    if use_tls:
                        server.starttls(context=ssl.create_default_context())
                    if password:
                        server.login(user, password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            return EmailResult(ok=True, detail="Email enviado")
        except Exception as exc:
            logger.exception("Error enviando SMTP")
            return EmailResult(ok=False, detail=str(exc))

    def send_user_welcome(
        self,
        *,
        to_email: str,
        name: str,
        password: str | None = None,
        login_url: str,
        tenant_slug: str,
        setup_url: str | None = None,
    ) -> EmailResult:
        """New-user email. Prefer *setup_url* (48h set-password link); never put a clear password in HTML when the link flow is used."""
        brand = self._brand()
        tpl = self._templates()["invite"]
        vars_ = {
            "name": name,
            "email": to_email,
            "tenant_slug": tenant_slug,
            "url": setup_url or login_url,
            "app_name": brand,
        }
        subject = render_template(tpl["subject"], **vars_)
        greeting = render_template(tpl["greeting"], **vars_)
        intro = render_template(tpl["intro"], **vars_)
        button = render_template(tpl["button_label"], **vars_)
        footer = render_template(tpl["footer"], **vars_)
        link_fallback = render_template(tpl.get("link_fallback", "Link:"), **vars_)

        if setup_url:
            body = (
                f"{greeting}\n\n{intro}\n\n{setup_url}\n\n"
                f"{footer}\n\n— {brand}\n"
            )
            html_body = _cta_html(
                greeting=greeting,
                intro=intro,
                button_label=button,
                url=setup_url,
                footer=footer,
                link_fallback=link_fallback,
                brand=brand,
            )
            return self._send(to_email, subject, body, html_body)

        # Legacy fallback: plaintext with temporary password (avoid when possible).
        body = (
            f"{greeting}\n\n"
            f"URL: {login_url}\n"
            f"Tenant: {tenant_slug}\n"
            f"Email: {to_email}\n"
            f"Contraseña: {password or '(definila al ingresar)'}\n\n"
            f"— {brand}\n"
        )
        return self._send(to_email, subject, body)

    def send_password_reset(
        self,
        *,
        to_email: str,
        name: str,
        password: str | None = None,
        login_url: str,
        reset_url: str | None = None,
    ) -> EmailResult:
        """Password-reset email; prefer *reset_url* link over sending a password."""
        brand = self._brand()
        tpl = self._templates()["reset"]
        vars_ = {
            "name": name,
            "email": to_email,
            "tenant_slug": "",
            "url": reset_url or login_url,
            "app_name": brand,
        }
        subject = render_template(tpl["subject"], **vars_)
        greeting = render_template(tpl["greeting"], **vars_)
        intro = render_template(tpl["intro"], **vars_)
        button = render_template(tpl["button_label"], **vars_)
        footer = render_template(tpl["footer"], **vars_)
        link_fallback = render_template(tpl.get("link_fallback", "Link:"), **vars_)

        if reset_url:
            body = f"{greeting}\n\n{intro}\n\n{reset_url}\n\n{footer}\n\n— {brand}\n"
            html_body = _cta_html(
                greeting=greeting,
                intro=intro,
                button_label=button,
                url=reset_url,
                footer=footer,
                link_fallback=link_fallback,
                brand=brand,
            )
            return self._send(to_email, subject, body, html_body)

        body = (
            f"{greeting}\n\n"
            f"URL: {login_url}\n"
            f"Email: {to_email}\n"
            f"Nueva contraseña: {password or ''}\n\n"
            f"— {brand}\n"
        )
        return self._send(to_email, subject, body)

    def test_connection(self) -> EmailResult:
        """Login-only probe (does not send a message)."""
        if not self._cfg:
            return EmailResult(ok=False, detail="SMTP no configurado")
        host = self._cfg.get("host", "")
        port = int(self._cfg.get("port", 587))
        user = self._cfg.get("user", "")
        password = self._cfg.get("password", "")
        use_tls = bool(self._cfg.get("starttls", True))
        try:
            if use_tls and port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                    server.login(user, password)
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    if use_tls:
                        server.starttls(context=ssl.create_default_context())
                    if password:
                        server.login(user, password)
            return EmailResult(ok=True, detail="Conexión SMTP OK")
        except Exception as exc:
            return EmailResult(ok=False, detail=str(exc))
