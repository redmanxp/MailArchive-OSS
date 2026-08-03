"""Email notification port."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailResult:
    ok: bool
    detail: str = ""


class INotifier(ABC):
    @abstractmethod
    def send_user_welcome(
        self,
        *,
        to_email: str,
        name: str,
        password: str | None = None,
        login_url: str,
        tenant_slug: str,
        setup_url: str | None = None,
    ) -> EmailResult: ...

    @abstractmethod
    def send_password_reset(
        self,
        *,
        to_email: str,
        name: str,
        password: str | None = None,
        login_url: str,
        reset_url: str | None = None,
    ) -> EmailResult: ...

    @abstractmethod
    def test_connection(self) -> EmailResult: ...
