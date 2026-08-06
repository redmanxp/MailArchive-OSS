"""User and tenant settings use cases."""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any

from app.config import Settings
from app.domain.enums.providers import AccountStatus
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.domain.interfaces.notifier import INotifier
from app.domain.interfaces.repositories import IAuditLogRepository, IPasswordHasher, IUserRepository
from app.infrastructure.email.smtp_notifier import SmtpNotifier
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
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
        must_change = must_change_password if password else True

        restored = self._user_repo.get_deleted_by_email(tenant_id, email)
        if restored is not None:
            user = self._user_repo.restore(
                tenant_id,
                restored.id,
                name=name,
                password_hash=password_hash,
                role=role,
                status=UserStatus.ACTIVE,
                must_change_password=must_change,
            )
            if user is None:
                raise ValidationError(f"No se pudo reactivar el usuario {email}")
            logger.info(
                "Recreating soft-deleted user email=%s as user_id=%s",
                email,
                user.id,
            )
            audit_action = "user.restore"
        else:
            user = self._user_repo.create(
                tenant_id=tenant_id,
                name=name,
                email=email,
                password_hash=password_hash,
                role=role,
                status=UserStatus.ACTIVE,
                must_change_password=must_change,
            )
            audit_action = "user.create"

        email_sent = False
        email_detail = ""
        setup_url = ""
        # Always issue invite link so admin can copy it if SMTP fails / is skipped
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
        if send_welcome_email:
            try:
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
            except Exception as exc:  # noqa: BLE001 — never roll back user create on mail failure
                email_sent = False
                email_detail = str(exc)
                logger.warning("Welcome email failed for %s: %s", user.email, exc)

        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action=audit_action,
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
            "setup_url": setup_url,
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
        mode = (self._settings.tenant_mode or "single").strip().lower()
        if mode not in ("single", "multi"):
            mode = "single"
        if mode == "single":
            tenants = self._tenant_repo.list_all()
            if len(tenants) != 1:
                raise NotFoundError("Organización (tenant) no encontrada")
            tenant = tenants[0]
        else:
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
        setup_url = ""
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
            setup_url = links.build_url(token)
            notifier = build_notifier(self._settings_repo, tenant_id, self._settings)
            result = notifier.send_password_reset(
                to_email=current.email,
                name=current.name,
                login_url=self._settings.app_url,
                reset_url=setup_url,
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
            "setup_url": setup_url,
        }


class DeactivateUserUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        audit_repo: IAuditLogRepository,
        account_repo: SqlAlchemyMailAccountRepository | None = None,
        archived_repo: SqlAlchemyArchivedMailRepository | None = None,
        job_repo: Any | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo
        self._account_repo = account_repo
        self._archived_repo = archived_repo
        self._job_repo = job_repo

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        user_id: int,
        accounts_action: str = "unlink",
        transfer_to_user_id: int | None = None,
    ) -> dict:
        """Deactivate user and handle their mail accounts.

        accounts_action:
          - unlink: soft-unlink all accounts (keep archive)
          - transfer: move accounts (+ mails) to transfer_to_user_id
        """
        if actor_user_id == user_id:
            raise ValidationError("No podés desactivar tu propio usuario")
        action = (accounts_action or "unlink").strip().lower()
        if action not in ("unlink", "transfer"):
            raise ValidationError("accounts_action must be unlink or transfer")

        accounts_touched = 0
        mails_moved = 0
        if self._account_repo is not None:
            owned = self._account_repo.list_for_user(tenant_id, user_id)
            if action == "transfer":
                if not transfer_to_user_id:
                    raise ValidationError("transfer_to_user_id is required when accounts_action=transfer")
                if transfer_to_user_id == user_id:
                    raise ValidationError("El destino debe ser otro usuario")
                target = self._user_repo.get_by_id(tenant_id, transfer_to_user_id)
                if target is None:
                    raise NotFoundError("Usuario destino no encontrado")
                status_val = getattr(target.status, "value", target.status)
                if status_val != UserStatus.ACTIVE.value:
                    raise ValidationError("El usuario destino debe estar activo")
                for acc in owned:
                    if acc.status == AccountStatus.UNLINKED.value:
                        # still transfer ownership of the archive shell
                        pass
                    if not self._account_repo.transfer_owner(tenant_id, acc.id, transfer_to_user_id):
                        raise ValidationError(
                            f"No se pudo transferir {acc.email}: el destino ya tiene esa cuenta"
                        )
                    if self._archived_repo is not None:
                        mails_moved += self._archived_repo.reassign_user_for_account(
                            tenant_id, acc.id, transfer_to_user_id
                        )
                    if self._job_repo is not None:
                        self._job_repo.reassign_user_for_account(
                            tenant_id, acc.id, transfer_to_user_id
                        )
                    accounts_touched += 1
            else:
                for acc in owned:
                    if acc.status == AccountStatus.UNLINKED.value:
                        continue
                    if self._job_repo is not None:
                        self._job_repo.fail_open_for_account(
                            tenant_id, acc.id, "Usuario desactivado; cuenta desvinculada"
                        )
                    self._account_repo.soft_unlink(tenant_id, acc.id)
                    accounts_touched += 1

        ok = self._user_repo.deactivate(tenant_id, user_id)
        if not ok:
            raise NotFoundError("Usuario no encontrado")
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.deactivate",
            resource_type="user",
            resource_id=str(user_id),
            details={
                "accounts_action": action,
                "transfer_to_user_id": transfer_to_user_id,
                "accounts_touched": accounts_touched,
                "mails_reassigned": mails_moved,
            },
        )
        return {
            "user_id": user_id,
            "accounts_action": action,
            "accounts_touched": accounts_touched,
            "mails_reassigned": mails_moved,
        }


class RestoreUserUseCase:
    """Reactivate a soft-deleted user (explicit admin action)."""

    def __init__(self, user_repo: IUserRepository, audit_repo: IAuditLogRepository) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, *, tenant_id: int, actor_user_id: int, user_id: int) -> dict:
        existing = self._user_repo.get_by_id_any(tenant_id, user_id)
        if existing is None:
            raise NotFoundError("Usuario no encontrado")
        if existing.deleted_at is None:
            raise ValidationError("El usuario ya está activo")
        # Keep current password hash; admin can send reset after.
        user = self._user_repo.restore(
            tenant_id,
            user_id,
            name=existing.name,
            password_hash=existing.password_hash,
            role=existing.role,
            status=UserStatus.ACTIVE,
            must_change_password=existing.must_change_password,
        )
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.restore",
            resource_type="user",
            resource_id=str(user_id),
            details={"email": user.email},
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "must_change_password": user.must_change_password,
        }


class HardDeleteUserUseCase:
    """Permanently delete a soft-deleted user. Never deletes EML archive."""

    def __init__(
        self,
        user_repo: IUserRepository,
        audit_repo: IAuditLogRepository,
        refresh_repo: Any,
        account_repo: SqlAlchemyMailAccountRepository | None = None,
        archived_repo: SqlAlchemyArchivedMailRepository | None = None,
        job_repo: Any | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo
        self._refresh_repo = refresh_repo
        self._account_repo = account_repo
        self._archived_repo = archived_repo
        self._job_repo = job_repo

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        user_id: int,
        reassign_to_user_id: int | None = None,
    ) -> dict:
        if actor_user_id == user_id:
            raise ValidationError("No podés eliminar tu propio usuario")
        existing = self._user_repo.get_by_id_any(tenant_id, user_id)
        if existing is None:
            raise NotFoundError("Usuario no encontrado")
        if existing.deleted_at is None:
            raise ValidationError("Desactivá el usuario antes del borrado definitivo")

        accounts_touched = 0
        mails_moved = 0
        owned = self._account_repo.list_for_user(tenant_id, user_id) if self._account_repo else []
        if owned:
            if not reassign_to_user_id:
                raise ValidationError(
                    "Este usuario aún tiene cuentas. Indicá reassign_to_user_id para transferirlas "
                    "(el archivo se conserva)."
                )
            if reassign_to_user_id == user_id:
                raise ValidationError("El destino debe ser otro usuario")
            target = self._user_repo.get_by_id(tenant_id, reassign_to_user_id)
            if target is None:
                raise NotFoundError("Usuario destino no encontrado")
            status_val = getattr(target.status, "value", target.status)
            if status_val != UserStatus.ACTIVE.value:
                raise ValidationError("El usuario destino debe estar activo")
            for acc in owned:
                if not self._account_repo.transfer_owner(tenant_id, acc.id, reassign_to_user_id):
                    raise ValidationError(
                        f"No se pudo transferir {acc.email}: el destino ya tiene esa cuenta"
                    )
                if self._archived_repo is not None:
                    mails_moved += self._archived_repo.reassign_user_for_account(
                        tenant_id, acc.id, reassign_to_user_id
                    )
                if self._job_repo is not None:
                    self._job_repo.reassign_user_for_account(
                        tenant_id, acc.id, reassign_to_user_id
                    )
                accounts_touched += 1

        tokens_deleted = 0
        if self._refresh_repo is not None:
            tokens_deleted = self._refresh_repo.delete_all_for_user(tenant_id, user_id)

        # Audit before nullify so we still have actor attribution on this event
        email = existing.email
        self._audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="user.hard_delete",
            resource_type="user",
            resource_id=str(user_id),
            details={
                "email": email,
                "accounts_reassigned": accounts_touched,
                "mails_reassigned": mails_moved,
                "reassign_to_user_id": reassign_to_user_id,
                "tokens_deleted": tokens_deleted,
            },
        )
        self._audit_repo.nullify_user(tenant_id, user_id)

        if not self._user_repo.hard_delete(tenant_id, user_id):
            raise NotFoundError("Usuario no encontrado")
        logger.info(
            "Hard-deleted user_id=%s email=%s accounts_reassigned=%s",
            user_id,
            email,
            accounts_touched,
        )
        return {
            "user_id": user_id,
            "email": email,
            "accounts_reassigned": accounts_touched,
            "mails_reassigned": mails_moved,
        }


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
