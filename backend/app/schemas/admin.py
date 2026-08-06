"""Admin API schemas."""

from pydantic import BaseModel, EmailStr, Field


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


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = None
    status: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    must_change_password: bool = True
    send_email: bool = True


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
    editable: bool = True
    restart_required: bool = False
    mysql_password_set: bool = False


class SystemSettingsUpdate(BaseModel):
    storage_root: str | None = None
    db_engine: str | None = None
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_user: str | None = None
    mysql_database: str | None = None
    mysql_password: str | None = None


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
