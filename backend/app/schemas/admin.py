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


class SmtpSettingsPublic(BaseModel):
    host: str = ""
    port: int = 587
    user: str = ""
    from_email: str = ""
    from_name: str = "MailArchive"
    starttls: bool = True
    enabled: bool = True
    configured: bool = False


class SmtpSettingsUpdate(BaseModel):
    host: str | None = None
    port: int | None = 587
    user: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    starttls: bool | None = True
    enabled: bool | None = True


class SmtpTestRequest(BaseModel):
    host: str | None = None
    port: int | None = 587
    user: str | None = None
    password: str | None = None
    from_email: str | None = None
    starttls: bool | None = True


class SmtpTestResponse(BaseModel):
    ok: bool
    detail: str
