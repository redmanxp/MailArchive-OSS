"""Domain enumerations."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    USER = "user"
    READONLY = "readonly"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"
