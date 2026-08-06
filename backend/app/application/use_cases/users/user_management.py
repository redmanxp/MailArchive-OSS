"""User and tenant settings use cases."""

from __future__ import annotations

import logging
import secrets
import string

from app.config import Settings
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.domain.interfaces.notifier import INotifier
from app.domain.interfaces.repositories import IAuditLogRepository, IPasswordHasher, IUserRepository
from app.infrastructure.email.smtp_notifier import SmtpNotifier
from app.infrastructure.persistence.repositories.tenant_settings_repo import SqlAlchemyTenantSettingsRepository
from app.infrastructure.security.password_link import PasswordLinkService

logger = logging.getLogger(__name__)


def build_notifier(settings_repo: SqlAlchemyTenantSettingsRepository, tenant_id: int, settings: Settings) -> INotifier:
    cfg = settings_repo.get_smtp_runtime(tenant_id)
    if cfg:
        return SmtpNotifier(cfg)
    # Fallback env
    if settings.smtp_host and settings.smtp_user:
        return SmtpNotifier(
            {
                "host": settings.smtp_host,
                "port": settings.smtp_port,
                "user": settings.smtp_user,
                "password": settings.smtp_password,
                "from_email": settings.smtp_from or settings.smtp_user,
                "from_name": settings.app_name,
                "reply_to": settings.smtp_reply_to,
                "timeout_seconds": settings.smtp_timeout_seconds,
                "starttls": settings.smtp_tls,
                "enabled": True,
            }
        )
    return SmtpNotifier(None)


def generate_temp_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _password_links(settings: Settings) -> PasswordLinkService:
    return PasswordLinkService(settings, ttl_hours=48)


class CreateUserUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        audit_repo: IAuditLogRepository,
        settings_repo: SqlAlchemyTenantSettingsRepository,
        settings: Settings,
        tenant_slug: str,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._audit_repo = audit_repo
        self._settings_repo = settings_repo
        self._settings = settings
        self._tenant_slug = tenant_slug

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int | None,
        name: str,
        email: str,
        role: UserRole,
        password: str | None = None,
        must_change_password: bool = True,
        send_welcome_email: bool = True,
    ) -> dict:
        name = name.strip()
        email = email.strip().lower()
        if not name or len(name) < 2:
            raise ValidationError("El nombre es obligatorio")
        if "@" not in email:
            raise ValidationError("Email inválido")
        if self._user_repo.get_by_email(tenant_id, email):
            raise ValidationError(f"Ya existe un usuario con email {email}")

        # Placeholder password until the user sets one via invite link
        raw_password = password if password and len(password) >= 8 else generate_temp_password()
        password_hash = self._password_hasher.hash(raw_password)

        user = self._user_repo.create(
            tenant_id=tenant_id,
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            status=UserStatus.ACTIVE,
            must_change_password=must_change_password if password else True,
        )
        email_sent = False
        email_detail = ""
        if send_welcome_email:
            links = _password_links(self._settings)
            token = links.issue(
                purpose="invite",
                tenant_id=tenant_id,
                user_id=user.id,
                email=user.email,
                name=user.name,
                password_hash=user.password_hash,
            )
            setup_url = links.build_url(token)
            notifier = build_notifier(self._settings_repo, tenant_id, self._settings)
            result = notifier.send_user_welcome(
                to_email=user.email,
                name=user.name,
                login_url=self._settings.app_url,
                tenant_slug=self._tenant_slug,
                setup_url=setup_url,
            )
            email_sent = result.ok
            email_detail = result.detail
            if not result.ok:
                logger.warning("No se pudo enviar email a %s: %s", user.email, result.detail)

        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.create",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email, "role": user.role.value, "email_sent": email_sent},
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "must_change_password": user.must_change_password,
            "email_sent": email_sent,
            "email_detail": email_detail,
        }


class SelfRegisterUseCase:
    """Public signup: create + invite link, or reset link if email already exists."""

    def __init__(
        self,
        tenant_repo,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        audit_repo: IAuditLogRepository,
        settings_repo: SqlAlchemyTenantSettingsRepository,
        settings: Settings,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._audit_repo = audit_repo
        self._settings_repo = settings_repo
        self._settings = settings

    def execute(
        self,
        *,
        tenant_slug: str,
        name: str,
        email: str,
    ) -> dict:
        slug = (tenant_slug or self._settings.install_tenant_slug).strip().lower()
        tenant = self._tenant_repo.get_by_slug(slug)
        if tenant is None:
            raise NotFoundError("Organización (tenant) no encontrada")

        email_norm = email.strip().lower()
        existing = self._user_repo.get_by_email(tenant.id, email_norm)
        if existing is not None:
            return self._send_reset_for_existing(tenant.id, tenant.slug, existing, name.strip() or existing.name)

        create = CreateUserUseCase(
            user_repo=self._user_repo,
            password_hasher=self._password_hasher,
            audit_repo=self._audit_repo,
            settings_repo=self._settings_repo,
            settings=self._settings,
            tenant_slug=tenant.slug,
        )
        result = create.execute(
            tenant_id=tenant.id,
            actor_user_id=None,
            name=name,
            email=email_norm,
            role=UserRole.USER,
            password=None,
            must_change_password=True,
            send_welcome_email=True,
        )
        self._audit_repo.add(
            tenant_id=tenant.id,
            user_id=result["id"],
            action="user.self_register",
            resource_type="user",
            resource_id=str(result["id"]),
            details={"email": result["email"], "email_sent": result["email_sent"]},
        )
        result["action"] = "created"
        result["message"] = (
            "Usuario creado. Revisá tu correo para definir la contraseña."
            if result["email_sent"]
            else f"Usuario creado. No se pudo enviar el email: {result.get('email_detail') or 'SMTP no configurado'}"
        )
        return result

    def _send_reset_for_existing(self, tenant_id: int, tenant_slug: str, user, name: str) -> dict:
        links = _password_links(self._settings)
        token = links.issue(
            purpose="reset",
            tenant_id=tenant_id,
            user_id=user.id,
            email=user.email,
            name=user.name,
            password_hash=user.password_hash,
        )
        reset_url = links.build_url(token)
        notifier = build_notifier(self._settings_repo, tenant_id, self._settings)
        result = notifier.send_password_reset(
            to_email=user.email,
            name=user.name,
            login_url=self._settings.app_url,
            reset_url=reset_url,
        )
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=user.id,
            action="user.self_register_existing",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email, "email_sent": result.ok, "tenant_slug": tenant_slug, "requested_name": name},
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "must_change_password": user.must_change_password,
            "email_sent": result.ok,
            "email_detail": result.detail,
            "action": "reset_sent",
            "message": (
                "Ese email ya está registrado. Te enviamos un enlace para restablecer la contraseña."
                if result.ok
                else f"Ese email ya está registrado. No se pudo enviar el enlace: {result.detail or 'SMTP no configurado'}"
            ),
        }


class PreviewPasswordLinkUseCase:
    def __init__(self, user_repo: IUserRepository, settings: Settings) -> None:
        self._user_repo = user_repo
        self._settings = settings

    def execute(self, token: str) -> dict:
        links = _password_links(self._settings)
        payload = links.verify(token)
        user = self._user_repo.get_by_id(int(payload["tenant_id"]), int(payload["user_id"]))
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        links.assert_still_valid(payload, user.password_hash)
        return {
            "name": user.name,
            "email": user.email,
            "purpose": payload["purpose"],
        }


class CompletePasswordLinkUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        audit_repo: IAuditLogRepository,
        settings: Settings,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._audit_repo = audit_repo
        self._settings = settings

    def execute(self, *, token: str, new_password: str) -> dict:
        if not new_password.strip():
            raise ValidationError("La contraseña es obligatoria")
        links = _password_links(self._settings)
        payload = links.verify(token)
        tenant_id = int(payload["tenant_id"])
        user_id = int(payload["user_id"])
        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("Usuario inactivo")
        links.assert_still_valid(payload, user.password_hash)

        updated = self._user_repo.update_password(
            tenant_id,
            user_id,
            self._password_hasher.hash(new_password),
            must_change_password=False,
        )
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action=f"user.password_{payload['purpose']}_complete",
            resource_type="user",
            resource_id=str(user_id),
            details={"purpose": payload["purpose"]},
        )
        return {
            "id": updated.id,
            "email": updated.email,
            "must_change_password": updated.must_change_password,
            "message": "Contraseña definida. Ya podés iniciar sesión.",
        }


class UpdateOwnProfileUseCase:
    def __init__(self, user_repo: IUserRepository, audit_repo: IAuditLogRepository) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, *, tenant_id: int, user_id: int, name: str) -> dict:
        name = name.strip()
        if len(name) < 2:
            raise ValidationError("El nombre es obligatorio")
        user = self._user_repo.update_profile(tenant_id, user_id, name=name)
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="user.profile_update",
            resource_type="user",
            resource_id=str(user_id),
        )
        return {
            "id": user.id,
            "tenant_id": user.tenant_id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "must_change_password": user.must_change_password,
        }


class UpdateUserUseCase:
    def __init__(self, user_repo: IUserRepository, audit_repo: IAuditLogRepository) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        user_id: int,
        name: str | None = None,
        role: UserRole | None = None,
        status: UserStatus | None = None,
    ) -> dict:
        user = self._user_repo.update_profile(
            tenant_id, user_id, name=name, role=role, status=status
        )
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.update",
            resource_type="user",
            resource_id=str(user_id),
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "must_change_password": user.must_change_password,
        }


class ResetPasswordUseCase:
    """Admin: send password-reset link (no plaintext password)."""

    def __init__(
        self,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        audit_repo: IAuditLogRepository,
        settings_repo: SqlAlchemyTenantSettingsRepository,
        settings: Settings,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._audit_repo = audit_repo
        self._settings_repo = settings_repo
        self._settings = settings

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        user_id: int,
        new_password: str | None = None,
        must_change_password: bool = True,
        send_email: bool = True,
    ) -> dict:
        user = self._user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado")

        # If admin still passes a password, set it; otherwise only send link
        if new_password:
            if len(new_password) < 8:
                raise ValidationError("La contraseña debe tener al menos 8 caracteres")
            updated = self._user_repo.update_password(
                tenant_id,
                user_id,
                self._password_hasher.hash(new_password),
                must_change_password=must_change_password,
            )
        else:
            updated = user

        email_sent = False
        email_detail = ""
        if send_email:
            links = _password_links(self._settings)
            # Re-fetch hash after optional password update
            current = self._user_repo.get_by_id(tenant_id, user_id)
            assert current is not None
            token = links.issue(
                purpose="reset",
                tenant_id=tenant_id,
                user_id=user_id,
                email=current.email,
                name=current.name,
                password_hash=current.password_hash,
            )
            reset_url = links.build_url(token)
            notifier = build_notifier(self._settings_repo, tenant_id, self._settings)
            result = notifier.send_password_reset(
                to_email=current.email,
                name=current.name,
                login_url=self._settings.app_url,
                reset_url=reset_url,
            )
            email_sent = result.ok
            email_detail = result.detail
            updated = current

        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.password_reset",
            resource_type="user",
            resource_id=str(user_id),
            details={"email_sent": email_sent, "set_password": bool(new_password)},
        )
        return {
            "id": updated.id,
            "email": updated.email,
            "email_sent": email_sent,
            "email_detail": email_detail,
        }


class DeactivateUserUseCase:
    def __init__(self, user_repo: IUserRepository, audit_repo: IAuditLogRepository) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, *, tenant_id: int, actor_user_id: int, user_id: int) -> None:
        if actor_user_id == user_id:
            raise ValidationError("No podés desactivar tu propio usuario")
        ok = self._user_repo.deactivate(tenant_id, user_id)
        if not ok:
            raise NotFoundError("Usuario no encontrado")
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.deactivate",
            resource_type="user",
            resource_id=str(user_id),
        )


class GetSmtpSettingsUseCase:
    def __init__(self, repo: SqlAlchemyTenantSettingsRepository) -> None:
        self._repo = repo

    def execute(self, tenant_id: int) -> dict:
        return self._repo.get_smtp_public(tenant_id)


class UpdateSmtpSettingsUseCase:
    def __init__(self, repo: SqlAlchemyTenantSettingsRepository, audit_repo: IAuditLogRepository) -> None:
        self._repo = repo
        self._audit_repo = audit_repo

    def execute(self, *, tenant_id: int, actor_user_id: int, payload: dict) -> dict:
        result = self._repo.update_smtp(tenant_id, payload)
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="settings.smtp_update",
            resource_type="tenant_settings",
            resource_id=str(tenant_id),
        )
        return result


class TestSmtpSettingsUseCase:
    def __init__(
        self,
        repo: SqlAlchemyTenantSettingsRepository,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._settings = settings

    def execute(self, tenant_id: int, payload: dict | None = None) -> dict:
        if payload and payload.get("host"):
            cfg = {
                "host": payload.get("host"),
                "port": int(payload.get("port", 587)),
                "user": payload.get("user"),
                "password": payload.get("password") or "",
                "from_email": payload.get("from_email") or payload.get("user"),
                "reply_to": payload.get("reply_to") or "",
                "timeout_seconds": payload.get("timeout_seconds") or 30,
                "starttls": bool(payload.get("starttls", True)),
                "enabled": True,
            }
            if not cfg["password"]:
                stored = self._repo.get_smtp_runtime(tenant_id)
                if stored:
                    cfg["password"] = stored.get("password", "")
                    if not cfg.get("timeout_seconds"):
                        cfg["timeout_seconds"] = stored.get("timeout_seconds") or 30
                    if not cfg.get("reply_to"):
                        cfg["reply_to"] = stored.get("reply_to") or ""
            notifier = SmtpNotifier(cfg)
        else:
            notifier = build_notifier(self._repo, tenant_id, self._settings)
        result = notifier.test_connection()
        return {"ok": result.ok, "detail": result.detail}
