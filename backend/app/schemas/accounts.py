"""Account / archive / search API schemas."""

from pydantic import BaseModel, EmailStr, Field


class AccountPublic(BaseModel):
    id: int
    user_id: int
    provider: str
    email: str
    display_name: str | None = None
    status: str
    last_sync_at: str | None = None
    last_error: str | None = None
    linked_at: str | None = None
    owner_email: str | None = None
    owner_name: str | None = None
    is_mine: bool = True
    imap_host: str | None = None
    imap_port: int | None = None
    imap_ssl: bool | None = None
    imap_username: str | None = None
    archived_count: int | None = None
    schedule_enabled: bool = False


class ImapTestRequest(BaseModel):
    host: str
    port: int = 993
    ssl: bool = True
    username: str
    password: str


class ImapCreateRequest(ImapTestRequest):
    email: EmailStr | None = None


class ConnectionTestResponse(BaseModel):
    ok: bool
    detail: str
    email: str | None = None


class OAuthStartResponse(BaseModel):
    authorize_url: str


class FolderPublic(BaseModel):
    id: str
    name: str
    path: str
    total_items: int | None = None


class ProviderMessagePublic(BaseModel):
    id: str
    subject: str
    from_address: str
    to_addresses: list[str] = Field(default_factory=list)
    sent_at: str | None = None
    received_at: str | None = None
    size_bytes: int = 0
    has_attachments: bool = False
    folder: str = ""


class AttachmentPublic(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int


class ProviderMessageDetail(ProviderMessagePublic):
    body_text: str | None = None
    body_html: str | None = None
    body_is_html: bool = False
    body_preview: str | None = None
    attachments: list[AttachmentPublic] = Field(default_factory=list)


class ArchiveMessageRequest(BaseModel):
    account_id: int
    message_id: str
    folder_id: str | None = None
    folder_path: str | None = None
    delete_after_archive: bool = False


class ArchiveMessageResponse(BaseModel):
    id: str
    subject: str
    size_bytes: int
    content_sha256: str
    deleted_from_provider: bool
    storage_path: str
    already_archived: bool = False


class ArchivedMailPublic(BaseModel):
    id: str
    account_id: int
    subject: str
    from_address: str
    to_addresses: str | None = None
    sent_at: str | None = None
    has_attachments: bool
    size_bytes: int
    archived_at: str | None = None
    body_preview: str | None = None
    deleted_from_provider: bool = False
    restored_at: str | None = None


class ArchivedMailSearchResponse(BaseModel):
    items: list[ArchivedMailPublic]
    total: int
    limit: int
    offset: int


class ArchivedMailIdsResponse(BaseModel):
    ids: list[str]
    total: int
    limit: int


class BulkMailIdsRequest(BaseModel):
    mail_ids: list[str] = Field(..., min_length=1, max_length=500)
    keep_copy: bool = False


class BulkRestoreResponse(BaseModel):
    restored: int
    failed: list[dict] = Field(default_factory=list)
    requested: int = 0
    kept_in_archive: bool = False


class BulkDeleteFromArchiveResponse(BaseModel):
    deleted: int
    failed: list[dict] = Field(default_factory=list)
    requested: int = 0


class DeleteFromArchiveResponse(BaseModel):
    id: str
    deleted: bool = True


class ArchivedMailDetail(ArchivedMailPublic):
    user_id: int
    provider_message_id: str
    folder_path: str = ""
    cc_addresses: str | None = None
    received_at: str | None = None
    content_sha256: str = ""
    body_text: str | None = None
    body_html: str | None = None
    body_is_html: bool = False
    attachment_names: str | None = None
    attachments: list[AttachmentPublic] = Field(default_factory=list)


class TransferAccountRequest(BaseModel):
    new_user_id: int
    reassign_mails: bool = True


class TransferAccountResponse(BaseModel):
    id: int
    from_user_id: int
    to_user_id: int
    mails_reassigned: int = 0
    jobs_reassigned: int = 0


class UnlinkAccountResponse(BaseModel):
    id: int
    status: str
    kept_archive: bool = True


class HardDeleteAccountResponse(BaseModel):
    id: int
    email: str
    jobs_deleted: int = 0


class PurgeAccountArchiveRequest(BaseModel):
    """Must type ELIMINAR (or DELETE) to purge archived EML + remove the account row."""

    confirm: str = Field(min_length=1, max_length=32)


class PurgeAccountArchiveResponse(BaseModel):
    id: int
    email: str
    mails_deleted: int = 0
    jobs_deleted: int = 0
    storage_errors: int = 0


class RestoreMailRequest(BaseModel):
    folder_id: str | None = None
    keep_copy: bool = False


class RestoreMailResponse(BaseModel):
    id: str
    provider_message_id: str
    folder: str
    account_id: int
    kept_in_archive: bool = False
