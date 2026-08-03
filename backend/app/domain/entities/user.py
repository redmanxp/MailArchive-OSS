"""Domain entity dataclasses (framework-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums.roles import TenantStatus, UserRole, UserStatus


@dataclass
class Tenant:
    id: int
    name: str
    slug: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class User:
    id: int
    tenant_id: int
    name: str
    email: str
    password_hash: str
    role: UserRole
    status: UserStatus
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class AuditLog:
    id: int
    tenant_id: int | None
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip: str | None
    user_agent: str | None
    details: dict | None
    created_at: datetime
