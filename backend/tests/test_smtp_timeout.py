"""SMTP notifier helper unit tests."""

from app.infrastructure.email.smtp_notifier import SmtpNotifier


def test_timeout_clamped() -> None:
    assert SmtpNotifier({"timeout_seconds": 2})._timeout() == 5.0
    assert SmtpNotifier({"timeout_seconds": 200})._timeout() == 120.0
    assert SmtpNotifier({"timeout_seconds": 45})._timeout() == 45.0
    assert SmtpNotifier({})._timeout() == 30.0
    assert SmtpNotifier({"timeout_seconds": "bad"})._timeout() == 30.0
