"""Bulk archive API schemas."""

from pydantic import BaseModel, Field


class BulkArchiveCriteria(BaseModel):
    folder_id: str | None = None
    folder_path: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    older_than_days: int | None = Field(default=None, ge=1, le=36500)
    min_size_bytes: int | None = Field(default=None, ge=0)
    only_with_attachments: bool = False


class BulkSimulateRequest(BaseModel):
    account_id: int
    criteria: BulkArchiveCriteria
    limit: int = Field(default=500, ge=1, le=2000)


class BulkSimulateResponse(BaseModel):
    account_id: int
    message_count: int
    total_bytes: int
    delete_after_archive: bool = False
    messages: list[dict] = Field(default_factory=list)
    sample: list[dict] = Field(default_factory=list)
    criteria: dict = Field(default_factory=dict)


class BulkStartRequest(BaseModel):
    account_id: int
    criteria: BulkArchiveCriteria
    delete_after_archive: bool = False
    limit: int = Field(default=500, ge=1, le=2000)
    message_ids: list[str] | None = None
    # Tamaños conocidos del preview (evita re-consultar Graph solo por bytes).
    total_bytes_hint: int | None = Field(default=None, ge=0)


class ArchiveJobPublic(BaseModel):
    id: int
    account_id: int
    user_id: int
    status: str
    criteria: dict | None = None
    delete_after_archive: bool
    total_messages: int
    processed_messages: int
    archived_messages: int
    skipped_messages: int
    failed_messages: int
    total_bytes: int
    archived_bytes: int
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    progress_pct: float = 0
