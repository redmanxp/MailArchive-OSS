"""SMTP password encrypt/decrypt round-trip (Fernet token string)."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import Settings
from app.infrastructure.security.fernet_cipher import CredentialCipher


def test_smtp_password_encrypt_decrypt_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    settings = Settings(
        data_encryption_key=key,
        secret_key="test-secret-key-please-change",
        jwt_secret_key="test-jwt-secret-please-change",
    )
    cipher = CredentialCipher(settings)
    token = cipher.encrypt_dict({"p": "SmtpPass123!"})
    assert isinstance(token, str)
    assert cipher.decrypt_dict(token)["p"] == "SmtpPass123!"
