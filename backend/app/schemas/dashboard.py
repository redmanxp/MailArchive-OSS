"""Dashboard metrics schemas."""

from pydantic import BaseModel, Field


class DashboardHealth(BaseModel):
    db_ok: bool = False
    storage_ok: bool = False
    storage_root: str | None = None


class DashboardMetricsResponse(BaseModel):
    tenant_id: int
    scope: str = Field(description="tenant | own")
    users_count: int | None = None
    accounts_count: int = 0
    mails_count: int = 0
    storage_bytes: int = 0
    attachments_count: int = 0
    jobs_active: int = 0
    jobs_failed: int = 0
    schedules_with_errors: int = 0
    last_archive_at: str | None = None
    health: DashboardHealth | None = None
    generated_at: str
