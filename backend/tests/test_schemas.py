"""Schema validation smoke tests."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import InstallRequest
from app.schemas.admin import MicrosoftSettingsUpdate, SmtpSettingsUpdate


def test_install_password_min_length() -> None:
    with pytest.raises(ValidationError):
        InstallRequest(
            tenant_name="Acme",
            tenant_slug="acme",
            admin_name="Admin",
            admin_email="admin@example.com",
            admin_password="short",
        )


def test_smtp_timeout_bounds() -> None:
    with pytest.raises(ValidationError):
        SmtpSettingsUpdate(timeout_seconds=2)
    with pytest.raises(ValidationError):
        SmtpSettingsUpdate(timeout_seconds=200)
    ok = SmtpSettingsUpdate(timeout_seconds=30)
    assert ok.timeout_seconds == 30


def test_microsoft_secret_rejects_guid_secret_id() -> None:
    with pytest.raises(ValidationError):
        MicrosoftSettingsUpdate(client_secret="1c3b53ea-4e54-4cfe-95ad-51ff4553ef76")
    ok = MicrosoftSettingsUpdate(client_secret="abc~not-a-guid-value-long-enough")
    assert ok.client_secret == "abc~not-a-guid-value-long-enough"


def test_microsoft_redirect_uri_strips_spaces() -> None:
    upd = MicrosoftSettingsUpdate(redirect_uri=" https://example.com/cb ")
    assert upd.redirect_uri == "https://example.com/cb"
