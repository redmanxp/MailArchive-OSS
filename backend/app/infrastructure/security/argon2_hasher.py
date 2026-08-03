"""Argon2 password hasher."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.domain.interfaces.repositories import IPasswordHasher


class Argon2PasswordHasher(IPasswordHasher):
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
