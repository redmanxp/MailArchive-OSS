"""Pydantic API schemas — Phase 0."""

from pydantic import BaseModel, EmailStr, Field


class InstallStatusResponse(BaseModel):
    installed: bool
    public_register_enabled: bool = False


class InstallRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=255)
    tenant_slug: str = Field(min_length=2, max_length=100)
    admin_name: str = Field(min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str | None = Field(default=None, min_length=1, max_length=128)


class InstallResponse(BaseModel):
    tenant_id: int
    tenant_slug: str
    admin_id: int
    admin_email: EmailStr
    temporary_password: str
    must_change_password: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str | None = None


class UserPublic(BaseModel):
    id: int
    tenant_id: int
    name: str
    email: EmailStr
    role: str
    must_change_password: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserPublic | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordResponse(BaseModel):
    id: int
    email: EmailStr
    must_change_password: bool


class MessageResponse(BaseModel):
    message: str


class SelfRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    tenant_slug: str | None = Field(default=None, max_length=100)


class SelfRegisterResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    email_sent: bool
    email_detail: str = ""
    action: str = "created"
    message: str = "Usuario creado. Revisá tu correo para definir la contraseña."


class PasswordLinkPreviewResponse(BaseModel):
    name: str
    email: EmailStr
    purpose: str


class CompletePasswordLinkRequest(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=1, max_length=128)


class CompletePasswordLinkResponse(BaseModel):
    id: int
    email: EmailStr
    must_change_password: bool
    message: str


class UpdateOwnProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class HealthResponse(BaseModel):
    status: str
    app: str
    phase: str
