"""Admin API schemas."""

from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_AZURE_SECRET_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class UserAdminPublic(BaseModel):
    id: int
    tenant_id: int
    name: str
    email: EmailStr
    role: str
    status: str
    must_change_password: bool


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    role: str = Field(default="user")
    password: str | None = Field(default=None, min_length=8, max_length=128)
    must_change_password: bool = True
    send_welcome_email: bool = True


class CreateUserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    status: str
    must_change_password: bool
    email_sent: bool
    email_detail: str = ""
    setup_url: str = ""


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = None
    status: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    must_change_password: bool = True
    send_email: bool = True


class ResetPasswordResponse(BaseModel):
    id: int
    email: EmailStr
    email_sent: bool
    email_detail: str = ""
    setup_url: str = ""


class DeactivateUserRequest(BaseModel):
    """What to do with the user's linked mail accounts when deactivating."""

    accounts_action: str = Field(
        default="unlink",
        description="unlink = soft-unlink keep archive; transfer = move accounts to another user",
    )
    transfer_to_user_id: int | None = None


class DepartureAccountItem(BaseModel):
    id: int
    email: EmailStr
    provider: str
    status: str


class DeparturePreviewResponse(BaseModel):
    """Wizard preview: user + linked (non-unlinked) accounts."""

    user: UserAdminPublic
    accounts: list[DepartureAccountItem]


class DepartureRequest(BaseModel):
    """Employee departure: optional bulk archive, then deactivate + account handling."""

    accounts_action: str = Field(
        default="transfer",
        description="transfer recommended when archiving; unlink clears credentials",
    )
    transfer_to_user_id: int | None = None
    archive_enabled: bool = False
    older_than_days: int | None = Field(default=None, ge=1, le=3650)
    archive_limit: int = Field(default=500, ge=1, le=2000)
    disable_schedules: bool = True


class DepartureSkipItem(BaseModel):
    account_id: int
    email: str
    reason: str


class DepartureResponse(BaseModel):
    user_id: int
    email: EmailStr
    deactivated: bool
    accounts_action: str
    accounts_touched: int
    mails_reassigned: int = 0
    job_ids: list[int] = Field(default_factory=list)
    archive_skipped: list[DepartureSkipItem] = Field(default_factory=list)
    schedules_disabled: int = 0


class HardDeleteUserRequest(BaseModel):
    """Permanent delete of a soft-deleted user. Archive is never purged here."""

    reassign_to_user_id: int | None = Field(
        default=None,
        description="Required if the user still owns mail accounts (including unlinked)",
    )


class EmailTemplateBlock(BaseModel):
    """One email kind (invite or reset): subject + body fragments for HTML CTA."""

    subject: str = ""
    greeting: str = ""
    intro: str = ""
    button_label: str = ""
    footer: str = ""
    link_fallback: str = ""


class EmailTemplatesPublic(BaseModel):
    """Tenant email copy for the active locale. Placeholders: {name} {email} {tenant_slug} {url} {app_name}."""

    locale: str = "es"
    invite: EmailTemplateBlock = Field(default_factory=EmailTemplateBlock)
    reset: EmailTemplateBlock = Field(default_factory=EmailTemplateBlock)


class LocaleOption(BaseModel):
    """Discovered language pack (from locales/*.json on disk)."""

    code: str
    name: str


class SmtpSettingsPublic(BaseModel):
    """SMTP settings returned to admins (password never included)."""

    host: str = ""
    port: int = 587
    user: str = ""
    from_email: str = ""
    from_name: str = "MailArchive"
    reply_to: str = ""
    timeout_seconds: int = 30
    starttls: bool = True
    enabled: bool = True
    configured: bool = False
    email_templates: EmailTemplatesPublic = Field(default_factory=EmailTemplatesPublic)
    available_locales: list[LocaleOption] = Field(default_factory=list)
    ui_locale: str = "es"


class SmtpSettingsUpdate(BaseModel):
    """Partial SMTP update. Omit password to keep the stored Fernet ciphertext."""

    host: str | None = None
    port: int | None = 587
    user: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    starttls: bool | None = True
    enabled: bool | None = True
    email_templates: EmailTemplatesPublic | None = None


class SmtpTestRequest(BaseModel):
    host: str | None = None
    port: int | None = 587
    user: str | None = None
    password: str | None = None
    from_email: str | None = None
    reply_to: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    starttls: bool | None = True


class SmtpTestResponse(BaseModel):
    ok: bool
    detail: str


class SystemSettingsPublic(BaseModel):
    """Data/storage config for admins (editable via file overrides)."""

    app_env: str
    db_engine: str
    database_label: str
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_database: str | None = None
    mysql_user: str | None = None
    storage_root: str
    storage_backend: str = "filesystem"
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    s3_prefix: str = ""
    s3_secret_set: bool = False
    editable: bool = True
    restart_required: bool = False
    mysql_password_set: bool = False
    tenant_mode: str = "single"
    tenant_count: int = 1


class SystemSettingsUpdate(BaseModel):
    storage_root: str | None = None
    storage_backend: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_force_path_style: bool | None = None
    s3_prefix: str | None = None
    db_engine: str | None = None
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_user: str | None = None
    mysql_database: str | None = None
    mysql_password: str | None = None
    tenant_mode: str | None = None


class MicrosoftSettingsPublic(BaseModel):
    client_id: str = ""
    tenant_id: str = "common"
    redirect_uri: str = ""
    configured: bool = False
    secret_set: bool = False


class MicrosoftSettingsUpdate(BaseModel):
    client_id: str | None = None
    tenant_id: str | None = None
    redirect_uri: str | None = None
    client_secret: str | None = None

    @field_validator("client_secret")
    @classmethod
    def client_secret_must_be_value_not_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            return cleaned
        # Azure "Secret ID" is a GUID; the usable credential is the longer "Value".
        if _AZURE_SECRET_ID.fullmatch(cleaned):
            raise ValueError(
                "Parece un Secret ID (GUID). En Azure copiá la columna Value del client secret, no el Secret ID."
            )
        return cleaned

    @field_validator("redirect_uri")
    @classmethod
    def strip_redirect_uri(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value
