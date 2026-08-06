"""Schema validation smoke tests."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import InstallRequest
from app.schemas.admin import SmtpSettingsUpdate


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
