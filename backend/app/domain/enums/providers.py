"""Mail provider and account enums."""

from enum import Enum


class MailProviderType(str, Enum):
    MICROSOFT365 = "microsoft365"
    IMAP = "imap"
    GMAIL = "gmail"


class AccountStatus(str, Enum):
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    UNLINKED = "unlinked"  # credentials cleared; archived mail kept
