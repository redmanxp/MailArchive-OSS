"""Account linking and archive use cases."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import Settings
from app.domain.enums.providers import AccountStatus, MailProviderType
from app.domain.enums.roles import UserRole, UserStatus
from app.domain.exceptions import AuthorizationError, DomainError, NotFoundError, ValidationError
from app.domain.interfaces.mail_provider import MessageQuery
from app.domain.interfaces.repositories import IAuditLogRepository
from app.infrastructure.persistence.repositories.mail_repos import (
    DeletedMail,
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_repos import SqlAlchemyUserRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.providers.imap_provider import ImapProvider
from app.infrastructure.providers.microsoft_graph import MicrosoftGraphProvider, MicrosoftOAuthService
from app.domain.interfaces.mail_storage import MailStorage, StoredAttachment
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure.storage.cas import (
    cas_att_key,
    cas_eml_key,
    identity_matches,
    normalize_rfc_message_id,
    rfc_message_id_from_eml,
)

import httpx

logger = logging.getLogger(__name__)


def _cleanup_mail_files(storage: MailStorage, deleted: DeletedMail | str | None) -> None:
    """Remove per-mail sidecar dir and CAS blobs that reached refcount 0."""
    if deleted is None:
        return
    if isinstance(deleted, str):
        storage.delete_mail_dir(deleted)
        return
    if deleted.storage_path:
        try:
            storage.delete_mail_dir(deleted.storage_path)
        except Exception:
            logger.exception("No se pudo borrar sidecar %s", deleted.storage_path)
    for blob_path in deleted.orphan_blob_paths:
        try:
            storage.delete_blob(blob_path)
        except Exception:
            logger.exception("No se pudo borrar blob CAS %s", blob_path)


class OAuthStateService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.secret_key.encode("utf-8")

    def issue(self, *, tenant_id: int, user_id: int) -> str:
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "nonce": str(uuid.uuid4()),
            "exp": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
        }
        raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def verify(self, state: str) -> dict[str, Any]:
        try:
            raw, sig = state.rsplit(".", 1)
        except ValueError as exc:
            raise ValidationError("State OAuth inválido") from exc
        expected = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValidationError("State OAuth inválido")
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        exp = datetime.fromisoformat(payload["exp"])
        if exp < datetime.now(UTC):
            raise ValidationError("State OAuth expirado")
        return payload


class StartMicrosoftOAuthUseCase:
    def __init__(self, settings: Settings, state_service: OAuthStateService) -> None:
        self.settings = settings
        self.state_service = state_service
        self.oauth = MicrosoftOAuthService(settings)

    def execute(self, *, tenant_id: int, user_id: int) -> dict:
        if not self.settings.microsoft_client_id or not self.settings.microsoft_client_secret:
            raise ValidationError("Microsoft OAuth no configurado en el servidor")
        state = self.state_service.issue(tenant_id=tenant_id, user_id=user_id)
        url = self.oauth.build_authorize_url(state)
        logger.info("Microsoft OAuth start user_id=%s tenant_id=%s", user_id, tenant_id)
        return {"authorize_url": url, "state": state}


class CompleteMicrosoftOAuthUseCase:
    def __init__(
        self,
        settings: Settings,
        state_service: OAuthStateService,
        account_repo: SqlAlchemyMailAccountRepository,
        cipher: CredentialCipher,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.settings = settings
        self.state_service = state_service
        self.account_repo = account_repo
        self.cipher = cipher
        self.audit_repo = audit_repo
        self.oauth = MicrosoftOAuthService(settings)

    def execute(self, *, code: str, state: str) -> dict:
        payload = self.state_service.verify(state)
        tenant_id = int(payload["tenant_id"])
        user_id = int(payload["user_id"])
        try:
            tokens = self.oauth.exchange_code(code)
        except httpx.HTTPStatusError as exc:
            raise ValidationError(str(exc)) from exc
        access = tokens["access_token"]
        refresh = tokens.get("refresh_token")
        expires_in = int(tokens.get("expires_in", 3600))
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        provider = MicrosoftGraphProvider(
            settings=self.settings,
            access_token=access,
            refresh_token=refresh,
            expires_at=expires_at,
        )
        result = provider.test_connection()
        if not result.ok or not result.email:
            raise ValidationError(f"No se pudo validar la cuenta Microsoft: {result.detail}")

        creds = {
            "access_token": access,
            "refresh_token": refresh,
            "expires_at": expires_at.isoformat(),
            "token_type": tokens.get("token_type", "Bearer"),
            "scope": tokens.get("scope"),
        }
        account = self.account_repo.upsert_microsoft(
            tenant_id=tenant_id,
            user_id=user_id,
            email=result.email,
            display_name=result.email,
            credentials_encrypted=self.cipher.encrypt_dict(creds),
            config={"graph": True},
        )
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.microsoft_linked",
            resource_type="mail_account",
            resource_id=str(account.id),
            details={"email": account.email},
        )
        logger.info("Microsoft account linked id=%s email=%s", account.id, account.email)
        return {
            "account_id": account.id,
            "email": account.email,
            "provider": account.provider,
            "status": account.status,
        }


class TestImapConnectionUseCase:
    def execute(
        self,
        *,
        host: str,
        port: int,
        ssl: bool,
        username: str,
        password: str,
    ) -> dict:
        provider = ImapProvider(host=host, port=port, ssl=ssl, username=username, password=password)
        result = provider.test_connection()
        return {"ok": result.ok, "detail": result.detail, "email": result.email}


class CreateImapAccountUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        cipher: CredentialCipher,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.account_repo = account_repo
        self.cipher = cipher
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        host: str,
        port: int,
        ssl: bool,
        username: str,
        password: str,
        email: str | None = None,
    ) -> dict:
        test = ImapProvider(host=host, port=port, ssl=ssl, username=username, password=password).test_connection()
        status = AccountStatus.CONNECTED.value if test.ok else AccountStatus.ERROR.value
        email_norm = (email or username).strip().lower()
        existing = self.account_repo.get_by_owner_email_provider(
            tenant_id, user_id, email_norm, MailProviderType.IMAP.value
        )
        creds = self.cipher.encrypt_dict(
            {"username": username, "password": password, "host": host, "port": port}
        )
        cfg = {"host": host, "port": port, "ssl": ssl, "username": username}
        if existing is not None:
            self.account_repo.update_credentials(
                tenant_id,
                existing.id,
                creds,
                config=cfg,
                status=status,
                last_error=None if test.ok else test.detail,
            )
            account = self.account_repo.get(tenant_id, existing.id)
            assert account is not None
            self.audit_repo.add(
                tenant_id=tenant_id,
                user_id=user_id,
                action="account.imap_reconnected",
                resource_type="mail_account",
                resource_id=str(account.id),
                details={"email": account.email, "ok": test.ok},
            )
            return {
                "id": account.id,
                "email": account.email,
                "provider": account.provider,
                "status": account.status,
                "last_error": account.last_error,
                "test_ok": test.ok,
                "test_detail": test.detail,
                "reconnected": True,
            }

        account = self.account_repo.create_imap(
            tenant_id=tenant_id,
            user_id=user_id,
            email=email_norm,
            config=cfg,
            credentials_encrypted=creds,
            status=status,
            last_error=None if test.ok else test.detail,
        )
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.imap_created",
            resource_type="mail_account",
            resource_id=str(account.id),
            details={"email": account.email, "ok": test.ok},
        )
        return {
            "id": account.id,
            "email": account.email,
            "provider": account.provider,
            "status": account.status,
            "last_error": account.last_error,
            "test_ok": test.ok,
            "test_detail": test.detail,
            "reconnected": False,
        }


class ListAccountsUseCase:
    """Usuario: solo sus cuentas. Admin/Supervisor: todas del tenant con dueño."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        user_repo: SqlAlchemyUserRepository | None = None,
        archived_repo: SqlAlchemyArchivedMailRepository | None = None,
        schedule_repo: Any | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.user_repo = user_repo
        self.archived_repo = archived_repo
        self.schedule_repo = schedule_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        status_filter: str | None = None,
    ) -> list[dict]:
        if role in (UserRole.ADMIN, UserRole.SUPERVISOR):
            accounts = self.account_repo.list_for_tenant(tenant_id)
        else:
            accounts = self.account_repo.list_for_user(tenant_id, user_id)

        filt = (status_filter or "").strip().lower()
        if filt in ("unlinked", "active"):
            if filt == "unlinked":
                accounts = [a for a in accounts if a.status == AccountStatus.UNLINKED.value]
            else:
                accounts = [a for a in accounts if a.status != AccountStatus.UNLINKED.value]

        owners: dict[int, Any] = {}
        if self.user_repo is not None and role in (UserRole.ADMIN, UserRole.SUPERVISOR):
            owners = {u.id: u for u in self.user_repo.list_by_tenant(tenant_id)}

        scheduled: set[int] = set()
        if self.schedule_repo is not None and filt != "unlinked":
            scheduled = self.schedule_repo.list_enabled_account_ids(tenant_id)

        items: list[dict] = []
        for a in accounts:
            cfg = getattr(a, "config", None) or {}
            archived_count = None
            if filt == "unlinked" and self.archived_repo is not None:
                archived_count = self.archived_repo.count_for_account(tenant_id, a.id)
            item = {
                "id": a.id,
                "user_id": a.user_id,
                "provider": a.provider,
                "email": a.email,
                "display_name": a.display_name,
                "status": a.status,
                "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
                "last_error": a.last_error,
                "linked_at": a.linked_at.isoformat() if a.linked_at else None,
                "owner_email": getattr(owners.get(a.user_id), "email", None),
                "owner_name": getattr(owners.get(a.user_id), "name", None),
                "is_mine": a.user_id == user_id,
                "imap_host": None,
                "imap_port": None,
                "imap_ssl": None,
                "imap_username": None,
                "archived_count": archived_count,
                "schedule_enabled": a.id in scheduled,
            }
            if a.provider == MailProviderType.IMAP.value and isinstance(cfg, dict):
                item["imap_host"] = cfg.get("host")
                item["imap_port"] = cfg.get("port")
                item["imap_ssl"] = cfg.get("ssl")
                item["imap_username"] = cfg.get("username")
            items.append(item)
        return items


class DeleteAccountUseCase:
    """Soft-unlink: clear credentials, keep account row and archived mail."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        audit_repo: IAuditLogRepository,
        job_repo: Any | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.audit_repo = audit_repo
        self.job_repo = job_repo

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, account_id: int) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede eliminar esta cuenta")
        if account.status == AccountStatus.UNLINKED.value:
            return {"id": account_id, "status": AccountStatus.UNLINKED.value, "kept_archive": True}

        if self.job_repo is not None:
            self.job_repo.fail_open_for_account(
                tenant_id, account_id, "Cuenta desvinculada; job cancelado"
            )
        ok = self.account_repo.soft_unlink(tenant_id, account_id)
        if not ok:
            raise NotFoundError("Cuenta no encontrada")
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.unlinked",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={"email": account.email, "kept_archive": True},
        )
        logger.info("Soft-unlinked account_id=%s email=%s kept_archive=true", account_id, account.email)
        return {"id": account_id, "status": AccountStatus.UNLINKED.value, "kept_archive": True}


class ReconnectImapAccountUseCase:
    """Restore credentials on an existing (usually unlinked) IMAP account row."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        cipher: CredentialCipher,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.account_repo = account_repo
        self.cipher = cipher
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        host: str,
        port: int,
        ssl: bool,
        username: str,
        password: str,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede reconectar esta cuenta")
        if account.provider != MailProviderType.IMAP.value:
            raise ValidationError("Solo cuentas IMAP se reconectan con este endpoint")

        test = ImapProvider(
            host=host, port=port, ssl=ssl, username=username, password=password
        ).test_connection()
        status = AccountStatus.CONNECTED.value if test.ok else AccountStatus.ERROR.value
        self.account_repo.update_credentials(
            tenant_id,
            account_id,
            self.cipher.encrypt_dict(
                {"username": username, "password": password, "host": host, "port": port}
            ),
            config={"host": host, "port": port, "ssl": ssl, "username": username},
            status=status,
            last_error=None if test.ok else test.detail,
        )
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.imap_reconnected",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={"email": account.email, "ok": test.ok},
        )
        return {
            "id": account_id,
            "email": account.email,
            "status": status,
            "test_ok": test.ok,
            "test_detail": test.detail,
        }


class HardDeleteAccountUseCase:
    """Delete account row only when no archived mail remains (EML never purged here)."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        archived_repo: SqlAlchemyArchivedMailRepository,
        audit_repo: IAuditLogRepository,
        job_repo: Any | None = None,
        schedule_repo: Any | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.archived_repo = archived_repo
        self.audit_repo = audit_repo
        self.job_repo = job_repo
        self.schedule_repo = schedule_repo

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, account_id: int) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede eliminar esta cuenta")
        if account.status != AccountStatus.UNLINKED.value:
            raise ValidationError("Desvinculá la cuenta antes del borrado definitivo")

        mail_count = self.archived_repo.count_for_account(tenant_id, account_id)
        if mail_count > 0:
            raise ValidationError(
                f"Hay {mail_count} correo(s) archivados. Usá «Purgar archivo» en Desvinculadas "
                "para borrarlos de forma definitiva, o dejá la cuenta desvinculada."
            )

        if self.schedule_repo is not None:
            self.schedule_repo.delete_for_account(tenant_id, account_id)
        jobs_deleted = 0
        if self.job_repo is not None:
            jobs_deleted = self.job_repo.delete_for_account(tenant_id, account_id)

        self.archived_repo.delete_exclusions_for_account(tenant_id, account_id)

        email = account.email
        if not self.account_repo.delete(tenant_id, account_id):
            raise NotFoundError("Cuenta no encontrada")
        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.hard_delete",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={"email": email, "jobs_deleted": jobs_deleted, "archived_kept": 0},
        )
        logger.info("Hard-deleted account_id=%s email=%s (no archived mails)", account_id, email)
        return {"id": account_id, "email": email, "jobs_deleted": jobs_deleted}


class PurgeAccountArchiveUseCase:
    """Delete all archived EML for an unlinked account, then remove the account row.

    Requires confirm phrase ELIMINAR (or DELETE). Irreversible.
    """

    CONFIRM_PHRASES = frozenset({"ELIMINAR", "DELETE"})

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        archived_repo: SqlAlchemyArchivedMailRepository,
        audit_repo: IAuditLogRepository,
        storage: MailStorage,
        job_repo: Any | None = None,
        schedule_repo: Any | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.archived_repo = archived_repo
        self.audit_repo = audit_repo
        self.storage = storage
        self.job_repo = job_repo
        self.schedule_repo = schedule_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        confirm: str,
    ) -> dict:
        phrase = (confirm or "").strip().upper()
        if phrase not in self.CONFIRM_PHRASES:
            raise ValidationError('Escribí ELIMINAR para confirmar la purga del archivo')

        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede purgar esta cuenta")
        if account.status != AccountStatus.UNLINKED.value:
            raise ValidationError("Desvinculá la cuenta antes de purgar el archivo")

        entries = self.archived_repo.list_ids_and_paths_for_account(tenant_id, account_id)
        mails_deleted = 0
        storage_errors = 0
        for mail_id, storage_path in entries:
            deleted = self.archived_repo.delete_mail(tenant_id, mail_id)
            mails_deleted += 1
            try:
                _cleanup_mail_files(self.storage, deleted)
                if deleted is None:
                    self.storage.delete_mail_dir(storage_path)
            except Exception:
                storage_errors += 1
                logger.exception(
                    "Purge: storage delete failed account_id=%s mail_id=%s path=%s",
                    account_id,
                    mail_id,
                    storage_path,
                )

        if self.schedule_repo is not None:
            self.schedule_repo.delete_for_account(tenant_id, account_id)
        jobs_deleted = 0
        if self.job_repo is not None:
            jobs_deleted = self.job_repo.delete_for_account(tenant_id, account_id)

        self.archived_repo.delete_exclusions_for_account(tenant_id, account_id)

        email = account.email
        if not self.account_repo.delete(tenant_id, account_id):
            raise NotFoundError("Cuenta no encontrada")

        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="account.purge_archive",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={
                "email": email,
                "mails_deleted": mails_deleted,
                "jobs_deleted": jobs_deleted,
                "storage_errors": storage_errors,
            },
        )
        logger.info(
            "Purged archive account_id=%s email=%s mails=%s storage_errors=%s",
            account_id,
            email,
            mails_deleted,
            storage_errors,
        )
        return {
            "id": account_id,
            "email": email,
            "mails_deleted": mails_deleted,
            "jobs_deleted": jobs_deleted,
            "storage_errors": storage_errors,
        }


class TransferAccountUseCase:
    """Admin: move linked account (+ archived mails) to another user in the same tenant."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        archived_repo: SqlAlchemyArchivedMailRepository,
        user_repo: SqlAlchemyUserRepository,
        audit_repo: IAuditLogRepository,
        job_repo: Any | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.archived_repo = archived_repo
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.job_repo = job_repo

    def execute(
        self,
        *,
        tenant_id: int,
        actor_user_id: int,
        role: UserRole,
        account_id: int,
        new_user_id: int,
        reassign_mails: bool = True,
    ) -> dict:
        if role != UserRole.ADMIN:
            raise AuthorizationError("Solo un administrador puede transferir cuentas")
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if account.user_id == new_user_id:
            raise ValidationError("La cuenta ya pertenece a ese usuario")
        target = self.user_repo.get_by_id(tenant_id, new_user_id)
        if target is None:
            raise NotFoundError("Usuario destino no encontrado")
        status_val = getattr(target.status, "value", target.status)
        if status_val != UserStatus.ACTIVE.value:
            raise ValidationError("El usuario destino debe estar activo")

        old_user_id = account.user_id
        if not self.account_repo.transfer_owner(tenant_id, account_id, new_user_id):
            raise ValidationError(
                "No se pudo transferir: el destino ya tiene esa cuenta (mismo email/proveedor)"
            )
        mails_moved = 0
        if reassign_mails:
            mails_moved = self.archived_repo.reassign_user_for_account(
                tenant_id, account_id, new_user_id
            )
        jobs_moved = 0
        if self.job_repo is not None:
            jobs_moved = self.job_repo.reassign_user_for_account(tenant_id, account_id, new_user_id)

        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="account.transferred",
            resource_type="mail_account",
            resource_id=str(account_id),
            details={
                "email": account.email,
                "from_user_id": old_user_id,
                "to_user_id": new_user_id,
                "mails_reassigned": mails_moved,
                "jobs_reassigned": jobs_moved,
            },
        )
        logger.info(
            "Transferred account_id=%s from user=%s to user=%s mails=%s",
            account_id,
            old_user_id,
            new_user_id,
            mails_moved,
        )
        return {
            "id": account_id,
            "from_user_id": old_user_id,
            "to_user_id": new_user_id,
            "mails_reassigned": mails_moved,
            "jobs_reassigned": jobs_moved,
        }


class TestAccountConnectionUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
    ) -> None:
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, account_id: int) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede probar esta cuenta")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        result = provider.test_connection()
        self.account_repo.set_status(
            tenant_id,
            account_id,
            AccountStatus.CONNECTED.value if result.ok else AccountStatus.ERROR.value,
            None if result.ok else result.detail,
        )
        return {"ok": result.ok, "detail": result.detail, "email": result.email}


class ListAccountFoldersUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
    ) -> None:
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, account_id: int) -> list[dict]:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede ver carpetas de esta cuenta")
        if account.status == AccountStatus.UNLINKED.value or not account.credentials_encrypted:
            raise ValidationError("Cuenta desvinculada: volvé a vincularla para usar el proveedor")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            folders = provider.list_folders()
            return [{"id": f.id, "name": f.name, "path": f.path, "total_items": f.total_items} for f in folders]
        finally:
            provider.disconnect()


class ListAccountMessagesUseCase:
    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
    ) -> None:
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        folder_id: str | None = None,
        limit: int = 50,
        only_with_attachments: bool = False,
    ) -> list[dict]:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede listar mensajes de esta cuenta")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            folder_ids = [folder_id] if folder_id else []
            messages = provider.list_messages(
                MessageQuery(
                    folder_ids=folder_ids,
                    limit=max(1, min(limit, 200)),
                    only_with_attachments=only_with_attachments,
                )
            )
            return [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "from_address": m.from_address,
                    "to_addresses": m.to_addresses,
                    "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                    "received_at": m.received_at.isoformat() if m.received_at else None,
                    "size_bytes": m.size_bytes,
                    "has_attachments": m.has_attachments,
                    "folder": m.folder,
                }
                for m in messages
            ]
        finally:
            provider.disconnect()


class PreviewProviderMessageUseCase:
    """Lee un mensaje del proveedor sin archivarlo (solo vista previa)."""

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
    ) -> None:
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        message_id: str,
        folder_id: str | None = None,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede ver mensajes de esta cuenta")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            raw = provider.download_message(message_id, folder=folder_id)
            text = raw.body_text or ""
            html = None
            is_html = False
            from app.infrastructure.storage.eml_utils import extract_bodies_from_eml, extract_file_attachments_from_eml
            from app.domain.interfaces.mail_provider import RawAttachment

            try:
                plain, html_body, preview = extract_bodies_from_eml(raw.eml_bytes)
                text = plain or text or preview
                html = html_body or None
                is_html = bool(html)
            except Exception:
                logger.exception("No se pudo reparsear EML para preview %s", message_id)

            attachments = list(raw.attachments or [])
            if not attachments and raw.eml_bytes:
                try:
                    for fname, ctype, content in extract_file_attachments_from_eml(raw.eml_bytes):
                        attachments.append(
                            RawAttachment(
                                filename=fname,
                                content_type=ctype,
                                size_bytes=len(content),
                                content=content,
                            )
                        )
                except Exception:
                    logger.exception("No se pudieron extraer adjuntos EML %s", message_id)

            return {
                "id": raw.provider_message_id,
                "subject": raw.subject,
                "from_address": raw.from_address,
                "to_addresses": raw.to_addresses,
                "sent_at": raw.sent_at.isoformat() if raw.sent_at else None,
                "received_at": raw.received_at.isoformat() if raw.received_at else None,
                "size_bytes": raw.size_bytes,
                "has_attachments": bool(attachments) or raw.has_attachments,
                "folder": raw.folder,
                "body_text": text or raw.body_preview,
                "body_html": html,
                "body_is_html": is_html,
                "body_preview": raw.body_preview,
                "attachments": [
                    {
                        "id": idx,
                        "filename": a.filename,
                        "content_type": a.content_type,
                        "size_bytes": a.size_bytes or len(a.content or b""),
                    }
                    for idx, a in enumerate(attachments)
                ],
            }
        finally:
            provider.disconnect()

    def download_attachment(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        message_id: str,
        attachment_id: int,
        folder_id: str | None = None,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede descargar adjuntos de esta cuenta")

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            raw = provider.download_message(message_id, folder=folder_id)
            attachments = list(raw.attachments or [])
            if not attachments and raw.eml_bytes:
                from app.infrastructure.storage.eml_utils import extract_file_attachments_from_eml
                from app.domain.interfaces.mail_provider import RawAttachment

                for fname, ctype, content in extract_file_attachments_from_eml(raw.eml_bytes):
                    attachments.append(
                        RawAttachment(
                            filename=fname,
                            content_type=ctype,
                            size_bytes=len(content),
                            content=content,
                        )
                    )
            if attachment_id < 0 or attachment_id >= len(attachments):
                raise NotFoundError("Adjunto no encontrado")
            att = attachments[attachment_id]
            return {
                "filename": att.filename,
                "content_type": att.content_type,
                "content": att.content or b"",
            }
        finally:
            provider.disconnect()


class ArchiveSingleMessageUseCase:
    _EXCLUDED = object()

    def __init__(
        self,
        account_repo: SqlAlchemyMailAccountRepository,
        archived_repo: SqlAlchemyArchivedMailRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
        storage: MailStorage,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.account_repo = account_repo
        self.archived_repo = archived_repo
        self.factory = factory
        self.cipher = cipher
        self.storage = storage
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        account_id: int,
        message_id: str,
        folder_id: str | None = None,
        folder_path: str | None = None,
        delete_after_archive: bool = False,
        internet_message_id: str | None = None,
        from_address: str | None = None,
        subject: str | None = None,
        sent_at: datetime | None = None,
    ) -> dict:
        account = self.account_repo.get(tenant_id, account_id)
        if account is None:
            raise NotFoundError("Cuenta no encontrada")
        if role not in (UserRole.ADMIN, UserRole.SUPERVISOR) and account.user_id != user_id:
            raise AuthorizationError("No puede archivar con esta cuenta")

        existing = self._find_existing_archived(
            tenant_id=tenant_id,
            account_id=account_id,
            provider=account.provider,
            message_id=message_id,
            folder_id=folder_id,
        )
        if existing is self._EXCLUDED:
            return self._excluded_result(message_id)
        if existing is not None:
            return self._handle_already_archived(
                account=account,
                existing=existing,
                tenant_id=tenant_id,
                user_id=user_id,
                account_id=account_id,
                message_id=message_id,
                folder_id=folder_id,
                delete_after_archive=delete_after_archive,
            )

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account_id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            rfc_id = normalize_rfc_message_id(internet_message_id)
            hint_from = from_address
            hint_subject = subject
            hint_sent = sent_at
            if not rfc_id:
                try:
                    summaries = provider.list_messages(
                        MessageQuery(
                            message_ids=[message_id],
                            folder_ids=[folder_id] if folder_id else [],
                            limit=1,
                        )
                    )
                    if summaries:
                        summary = summaries[0]
                        rfc_id = normalize_rfc_message_id(summary.internet_message_id)
                        hint_from = hint_from or summary.from_address
                        hint_subject = summary.subject if hint_subject is None else hint_subject
                        hint_sent = hint_sent or summary.sent_at
                        folder_id = folder_id or summary.folder
                        folder_path = folder_path or summary.folder
                except Exception:
                    logger.exception(
                        "Light metadata fetch failed account=%s msg=%s", account_id, message_id
                    )
            if rfc_id:
                linked = self._try_link_shared(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                    rfc_id=rfc_id,
                    from_address=hint_from or "",
                    subject=hint_subject or "",
                    sent_at=hint_sent,
                    provider_message_id=message_id,
                    folder_path=folder_path or folder_id or "",
                    delete_after_archive=delete_after_archive,
                    provider=provider,
                    message_id=message_id,
                    folder_id=folder_id,
                )
                if linked is not None:
                    return linked

            raw = provider.download_message(message_id, folder=folder_id)
            content_sha = hashlib.sha256(raw.eml_bytes or b"").hexdigest() if raw.eml_bytes else None
            rfc_id = rfc_message_id_from_eml(raw.eml_bytes or b"") or rfc_id
            if rfc_id:
                linked = self._try_link_shared(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                    rfc_id=rfc_id,
                    from_address=raw.from_address,
                    subject=raw.subject,
                    sent_at=raw.sent_at,
                    provider_message_id=raw.provider_message_id or message_id,
                    folder_path=folder_path or raw.folder or folder_id or "",
                    delete_after_archive=delete_after_archive,
                    provider=provider,
                    message_id=message_id,
                    folder_id=folder_id,
                    to_addresses=",".join(raw.to_addresses),
                    cc_addresses=",".join(raw.cc_addresses),
                    received_at=raw.received_at,
                )
                if linked is not None:
                    return linked
            # Re-check after download (scheduled job may have archived meanwhile;
            # IMAP also matches legacy bare-UID rows + content hash).
            existing = self._find_existing_archived(
                tenant_id=tenant_id,
                account_id=account_id,
                provider=account.provider,
                message_id=raw.provider_message_id or message_id,
                folder_id=folder_id or raw.folder,
                content_sha256=content_sha,
            )
            if existing is self._EXCLUDED:
                return self._excluded_result(raw.provider_message_id or message_id)
            if existing is not None:
                if account.provider == MailProviderType.IMAP.value:
                    self._maybe_normalize_provider_id(
                        existing, raw.provider_message_id or message_id
                    )
                deleted = bool(existing.deleted_from_provider)
                if delete_after_archive and not deleted:
                    provider.delete_message(message_id, folder=folder_id)
                    self.archived_repo.mark_deleted_from_provider(tenant_id, existing.id)
                    deleted = True
                    self.audit_repo.add(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="mail.deleted_from_provider",
                        resource_type="archived_mail",
                        resource_id=existing.id,
                        details={"account_id": account_id},
                    )
                return {
                    "id": existing.id,
                    "subject": existing.subject,
                    "size_bytes": existing.size_bytes,
                    "content_sha256": existing.content_sha256,
                    "deleted_from_provider": deleted,
                    "storage_path": existing.storage_path,
                    "already_archived": True,
                }

            mail_id = str(uuid.uuid4())
            stored = self.storage.save_message(
                tenant_id=tenant_id,
                account_id=account_id,
                mail_id=mail_id,
                raw=raw,
            )
            try:
                self.archived_repo.create(
                    mail_id=mail_id,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    user_id=user_id,
                    provider_message_id=raw.provider_message_id,
                    folder_path=(folder_path or raw.folder or folder_id or ""),
                    subject=raw.subject,
                    from_address=raw.from_address,
                    to_addresses=",".join(raw.to_addresses),
                    cc_addresses=",".join(raw.cc_addresses),
                    sent_at=raw.sent_at,
                    received_at=raw.received_at,
                    has_attachments=raw.has_attachments,
                    size_bytes=raw.size_bytes,
                    content_sha256=stored.content_sha256,
                    storage_path=stored.relative_dir,
                    body_preview=raw.body_preview,
                    body_text=raw.body_text,
                    attachment_names=",".join(a.filename for a in raw.attachments),
                    deleted_from_provider=False,
                    rfc_message_id=rfc_id,
                    attachments=[
                        {
                            "filename": a.filename,
                            "content_type": a.content_type,
                            "size_bytes": a.size_bytes,
                            "sha256": a.sha256,
                            "storage_path": a.relative_path,
                        }
                        for a in stored.attachments
                    ],
                )
            except Exception as exc:
                # Race: another worker inserted the same provider_message_id
                from sqlalchemy.exc import IntegrityError

                if not isinstance(exc, IntegrityError):
                    raise
                logger.info(
                    "Archive race: message already archived account=%s msg=%s",
                    account_id,
                    message_id,
                )
                self.archived_repo._db.rollback()
                raced = self._find_existing_archived(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    provider=account.provider,
                    message_id=raw.provider_message_id or message_id,
                    folder_id=folder_id or raw.folder,
                    content_sha256=hashlib.sha256(raw.eml_bytes or b"").hexdigest() if raw.eml_bytes else None,
                )
                if raced is self._EXCLUDED:
                    return self._excluded_result(raw.provider_message_id or message_id)
                if raced is None:
                    raise
                deleted = bool(raced.deleted_from_provider)
                if delete_after_archive and not deleted:
                    provider.delete_message(message_id, folder=folder_id)
                    self.archived_repo.mark_deleted_from_provider(tenant_id, raced.id)
                    deleted = True
                return {
                    "id": raced.id,
                    "subject": raced.subject,
                    "size_bytes": raced.size_bytes,
                    "content_sha256": raced.content_sha256,
                    "deleted_from_provider": deleted,
                    "storage_path": raced.storage_path,
                    "already_archived": True,
                }

            # Persist before provider delete / further I/O to release SQLite write lock
            from app.infrastructure.persistence.database import commit_with_retry

            self.audit_repo.add(
                tenant_id=tenant_id,
                user_id=user_id,
                action="mail.archived",
                resource_type="archived_mail",
                resource_id=mail_id,
                details={"account_id": account_id, "deleted_from_provider": False},
            )
            commit_with_retry(self.archived_repo._db)

            deleted = False
            if delete_after_archive:
                provider.delete_message(message_id, folder=folder_id)
                self.archived_repo.mark_deleted_from_provider(tenant_id, mail_id)
                deleted = True
                self.audit_repo.add(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="mail.deleted_from_provider",
                    resource_type="archived_mail",
                    resource_id=mail_id,
                    details={"account_id": account_id},
                )
            return {
                "id": mail_id,
                "subject": raw.subject,
                "size_bytes": raw.size_bytes,
                "content_sha256": stored.content_sha256,
                "deleted_from_provider": deleted,
                "storage_path": stored.relative_dir,
                "already_archived": False,
            }
        finally:
            provider.disconnect()

    def _ensure_donor_cas(self, donor: Any) -> tuple[str, list[dict[str, Any]]] | None:
        try:
            eml_bytes = self.storage.read_eml_from_dir(donor.storage_path)
        except FileNotFoundError:
            logger.warning("Donor EML missing mail_id=%s path=%s", donor.id, donor.storage_path)
            return None
        eml_sha = donor.content_sha256 or hashlib.sha256(eml_bytes).hexdigest()
        eml_key = cas_eml_key(donor.tenant_id, eml_sha)
        self.storage.put_blob_if_absent(eml_key, eml_bytes, "message/rfc822")
        att_payload: list[dict[str, Any]] = []
        for att in self.archived_repo.list_attachments(donor.tenant_id, donor.id):
            try:
                data = self.storage.read_attachment(att.storage_path)
            except FileNotFoundError:
                logger.warning("Donor attachment missing mail=%s att=%s", donor.id, att.id)
                continue
            sha = att.sha256 or hashlib.sha256(data).hexdigest()
            key = cas_att_key(donor.tenant_id, sha)
            self.storage.put_blob_if_absent(key, data, att.content_type or "application/octet-stream")
            if att.storage_path != key:
                att.storage_path = key
            if att.sha256 != sha:
                att.sha256 = sha
            att_payload.append(
                {
                    "filename": att.filename,
                    "content_type": att.content_type,
                    "size_bytes": att.size_bytes,
                    "sha256": sha,
                    "storage_path": key,
                }
            )
        if donor.content_sha256 != eml_sha:
            donor.content_sha256 = eml_sha
        self.archived_repo._db.flush()
        return eml_sha, att_payload

    def _try_link_shared(
        self,
        *,
        tenant_id: int,
        user_id: int,
        account_id: int,
        rfc_id: str,
        from_address: str,
        subject: str,
        sent_at: datetime | None,
        provider_message_id: str,
        folder_path: str,
        delete_after_archive: bool,
        provider: Any,
        message_id: str,
        folder_id: str | None,
        to_addresses: str | None = None,
        cc_addresses: str | None = None,
        received_at: datetime | None = None,
    ) -> dict | None:
        donor = self.archived_repo.get_by_rfc_message_id(tenant_id, rfc_id)
        if donor is None or donor.account_id == account_id:
            return None
        if not identity_matches(
            donor_from=donor.from_address,
            donor_subject=donor.subject,
            donor_sent_at=donor.sent_at,
            from_address=from_address,
            subject=subject,
            sent_at=sent_at,
        ):
            logger.warning(
                "Skip blob share: Message-ID match but identity differs donor=%s account=%s rfc=%s",
                donor.id,
                account_id,
                rfc_id[:48],
            )
            return None
        promoted = self._ensure_donor_cas(donor)
        if promoted is None:
            return None
        eml_sha, att_payload = promoted
        self.archived_repo.ensure_blob(
            tenant_id=tenant_id,
            sha256=eml_sha,
            kind="eml",
            size_bytes=int(donor.size_bytes or 0),
            storage_path=cas_eml_key(tenant_id, eml_sha),
        )
        for att in att_payload:
            self.archived_repo.ensure_blob(
                tenant_id=tenant_id,
                sha256=att["sha256"],
                kind="att",
                size_bytes=int(att.get("size_bytes") or 0),
                storage_path=att["storage_path"],
            )
        stored_atts = [
            StoredAttachment(
                filename=a["filename"],
                content_type=a["content_type"] or "application/octet-stream",
                size_bytes=int(a["size_bytes"] or 0),
                sha256=a["sha256"],
                relative_path=a["storage_path"],
            )
            for a in att_payload
        ]
        mail_id = str(uuid.uuid4())
        rel_dir = self.storage.write_mail_sidecar(
            tenant_id=tenant_id,
            account_id=account_id,
            mail_id=mail_id,
            content_sha256=eml_sha,
            attachments=stored_atts,
            extra_metadata={
                "provider_message_id": provider_message_id,
                "subject": subject or donor.subject,
                "from": from_address or donor.from_address,
                "shared_from_mail_id": donor.id,
                "size_bytes": donor.size_bytes,
            },
        )
        try:
            self.archived_repo.create(
                mail_id=mail_id,
                tenant_id=tenant_id,
                account_id=account_id,
                user_id=user_id,
                provider_message_id=provider_message_id,
                folder_path=folder_path or donor.folder_path or "",
                subject=subject or donor.subject,
                from_address=from_address or donor.from_address,
                to_addresses=to_addresses if to_addresses is not None else (donor.to_addresses or ""),
                cc_addresses=cc_addresses if cc_addresses is not None else (donor.cc_addresses or ""),
                sent_at=sent_at or donor.sent_at,
                received_at=received_at or donor.received_at,
                has_attachments=bool(att_payload) or bool(donor.has_attachments),
                size_bytes=int(donor.size_bytes or 0),
                content_sha256=eml_sha,
                storage_path=rel_dir,
                body_preview=donor.body_preview,
                body_text=donor.body_text,
                attachment_names=donor.attachment_names,
                deleted_from_provider=False,
                rfc_message_id=rfc_id,
                attachments=att_payload,
            )
        except Exception:
            logger.exception("Shared-blob link insert failed account=%s rfc=%s", account_id, rfc_id[:48])
            return None

        from app.infrastructure.persistence.database import commit_with_retry

        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="mail.archived",
            resource_type="archived_mail",
            resource_id=mail_id,
            details={
                "account_id": account_id,
                "shared_from_mail_id": donor.id,
                "rfc_message_id": rfc_id,
            },
        )
        commit_with_retry(self.archived_repo._db)

        deleted = False
        if delete_after_archive:
            provider.delete_message(message_id, folder=folder_id)
            self.archived_repo.mark_deleted_from_provider(tenant_id, mail_id)
            deleted = True
            self.audit_repo.add(
                tenant_id=tenant_id,
                user_id=user_id,
                action="mail.deleted_from_provider",
                resource_type="archived_mail",
                resource_id=mail_id,
                details={"account_id": account_id},
            )
        logger.info(
            "Archived via shared blob mail_id=%s donor=%s account=%s rfc=%s",
            mail_id,
            donor.id,
            account_id,
            rfc_id[:48],
        )
        return {
            "id": mail_id,
            "subject": subject or donor.subject,
            "size_bytes": int(donor.size_bytes or 0),
            "content_sha256": eml_sha,
            "deleted_from_provider": deleted,
            "storage_path": rel_dir,
            "already_archived": False,
            "shared_blob": True,
        }

    def _find_existing_archived(
        self,
        *,
        tenant_id: int,
        account_id: int,
        provider: str,
        message_id: str,
        folder_id: str | None = None,
        content_sha256: str | None = None,
    ) -> Any:
        """Resolve already-archived row; IMAP matches legacy bare UID + composite aliases."""
        if provider == MailProviderType.IMAP.value:
            candidates = ImapProvider.message_id_aliases(message_id, folder_id)
        else:
            candidates = [message_id] if message_id else []

        if self.archived_repo.is_excluded(
            tenant_id,
            account_id,
            provider_message_ids=candidates,
            content_sha256=content_sha256,
        ):
            return ArchiveSingleMessageUseCase._EXCLUDED

        if provider == MailProviderType.IMAP.value:
            existing = self.archived_repo.find_by_provider_message_ids(
                tenant_id, account_id, candidates
            )
        else:
            existing = self.archived_repo.get_by_provider_message_id(
                tenant_id, account_id, message_id
            )
        if existing is None and content_sha256:
            existing = self.archived_repo.get_by_content_sha256(
                tenant_id, account_id, content_sha256
            )
        return existing

    def _excluded_result(self, message_id: str) -> dict:
        return {
            "id": None,
            "subject": "",
            "size_bytes": 0,
            "content_sha256": "",
            "deleted_from_provider": False,
            "storage_path": "",
            "already_archived": True,
            "excluded": True,
            "message_id": message_id,
        }

    def _maybe_normalize_provider_id(self, existing: Any, new_id: str) -> None:
        """Upgrade legacy plain IMAP UID to folder\\x1fuid when safe."""
        if not new_id or existing.provider_message_id == new_id:
            return
        # Only upgrade toward composite ids (never replace composite with bare UID).
        if ImapProvider._ID_SEP not in new_id:
            return
        clash = self.archived_repo.get_by_provider_message_id(
            existing.tenant_id, existing.account_id, new_id
        )
        if clash is not None and clash.id != existing.id:
            return
        logger.info(
            "Normalize provider_message_id mail=%s %r -> %r",
            existing.id,
            existing.provider_message_id,
            new_id,
        )
        existing.provider_message_id = new_id
        self.archived_repo._db.flush()

    def _handle_already_archived(
        self,
        *,
        account: Any,
        existing: Any,
        tenant_id: int,
        user_id: int,
        account_id: int,
        message_id: str,
        folder_id: str | None,
        delete_after_archive: bool,
    ) -> dict:
        if account.provider == MailProviderType.IMAP.value:
            self._maybe_normalize_provider_id(existing, message_id)
        deleted = bool(existing.deleted_from_provider)
        if delete_after_archive and not deleted:
            def _persist(tokens: dict[str, Any]) -> None:
                self.account_repo.update_credentials(
                    tenant_id, account_id, self.cipher.encrypt_dict(tokens)
                )

            provider = self.factory.create(
                provider=account.provider,
                config=account.config,
                credentials_encrypted=account.credentials_encrypted,
                on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
            )
            provider.connect()
            try:
                provider.delete_message(message_id, folder=folder_id)
                self.archived_repo.mark_deleted_from_provider(tenant_id, existing.id)
                deleted = True
                self.audit_repo.add(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="mail.deleted_from_provider",
                    resource_type="archived_mail",
                    resource_id=existing.id,
                    details={"account_id": account_id},
                )
            finally:
                provider.disconnect()
        logger.info(
            "Message already archived account=%s mail=%s delete=%s",
            account_id,
            existing.id,
            deleted,
        )
        return {
            "id": existing.id,
            "subject": existing.subject,
            "size_bytes": existing.size_bytes,
            "content_sha256": existing.content_sha256,
            "deleted_from_provider": deleted,
            "storage_path": existing.storage_path,
            "already_archived": True,
        }


class SearchArchivedMailsUseCase:
    def __init__(self, archived_repo: SqlAlchemyArchivedMailRepository) -> None:
        self.archived_repo = archived_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        q: str | None = None,
        account_id: int | None = None,
        from_address: str | None = None,
        has_attachments: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        scope_user = None if role in (UserRole.ADMIN, UserRole.SUPERVISOR) else user_id
        rows, total = self.archived_repo.search(
            tenant_id,
            user_id=scope_user,
            q=q,
            account_id=account_id,
            from_address=from_address,
            has_attachments=has_attachments,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        items = [
            {
                "id": r.id,
                "account_id": r.account_id,
                "subject": r.subject,
                "from_address": r.from_address,
                "to_addresses": r.to_addresses,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "has_attachments": r.has_attachments,
                "size_bytes": r.size_bytes,
                "archived_at": r.archived_at.isoformat() if r.archived_at else None,
                "body_preview": r.body_preview,
                "deleted_from_provider": r.deleted_from_provider,
                "restored_at": r.restored_at.isoformat() if r.restored_at else None,
            }
            for r in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def search_ids(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        q: str | None = None,
        account_id: int | None = None,
        from_address: str | None = None,
        has_attachments: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 2000,
    ) -> dict:
        scope_user = None if role in (UserRole.ADMIN, UserRole.SUPERVISOR) else user_id
        ids, total = self.archived_repo.search_ids(
            tenant_id,
            user_id=scope_user,
            q=q,
            account_id=account_id,
            from_address=from_address,
            has_attachments=has_attachments,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return {"ids": ids, "total": total, "limit": limit}


def _can_access_mail(role: UserRole, user_id: int, mail_user_id: int) -> bool:
    if role in (UserRole.ADMIN, UserRole.SUPERVISOR):
        return True
    return mail_user_id == user_id


def _can_restore_to_account(role: UserRole, user_id: int, account: Any) -> bool:
    """Usuario: solo sus cuentas vinculadas. Admin/Supervisor: cualquier cuenta activa del tenant."""
    if getattr(account, "status", None) == AccountStatus.UNLINKED.value:
        return False
    if role in (UserRole.ADMIN, UserRole.SUPERVISOR):
        return True
    return account.user_id == user_id


class GetArchivedMailUseCase:
    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        storage: MailStorage | None = None,
        account_repo: SqlAlchemyMailAccountRepository | None = None,
        factory: MailProviderFactory | None = None,
        cipher: CredentialCipher | None = None,
    ) -> None:
        self.archived_repo = archived_repo
        self.storage = storage
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, mail_id: str) -> dict:
        from app.infrastructure.storage.eml_utils import extract_bodies_from_eml, looks_like_graph_folder_id

        row = self.archived_repo.get(tenant_id, mail_id)
        if row is None:
            raise NotFoundError("Correo archivado no encontrado")
        if not _can_access_mail(role, user_id, row.user_id):
            raise AuthorizationError("No puede ver este correo")
        attachments = self.archived_repo.list_attachments(tenant_id, mail_id)

        body_text = row.body_text or ""
        body_html = ""
        folder_path = row.folder_path or ""

        if self.storage:
            try:
                eml = self.storage.read_eml_from_dir(row.storage_path)
                plain, html, _preview = extract_bodies_from_eml(eml)
                if plain:
                    body_text = plain
                if html:
                    body_html = html
                if not body_text and html:
                    from app.infrastructure.storage.eml_utils import html_to_text

                    body_text = html_to_text(html)
            except Exception:
                logger.exception("No se pudo reparsear EML mail_id=%s", mail_id)

        if not body_html and body_text and "<html" in body_text.lower():
            body_html = body_text

        if looks_like_graph_folder_id(folder_path) and self.account_repo and self.factory and self.cipher:
            try:
                account = self.account_repo.get(tenant_id, row.account_id)
                if account and account.provider == "microsoft365":

                    def _persist(tokens: dict[str, Any]) -> None:
                        self.account_repo.update_credentials(  # type: ignore[union-attr]
                            tenant_id, account.id, self.cipher.encrypt_dict(tokens)  # type: ignore[union-attr]
                        )

                    provider = self.factory.create(
                        provider=account.provider,
                        config=account.config,
                        credentials_encrypted=account.credentials_encrypted,
                        on_tokens_refreshed=_persist,
                    )
                    provider.connect()
                    try:
                        if hasattr(provider, "_resolve_folder_label"):
                            resolved = provider._resolve_folder_label(folder_path)  # noqa: SLF001
                            if resolved and not looks_like_graph_folder_id(resolved):
                                folder_path = resolved
                                self.archived_repo.update_folder_path(tenant_id, mail_id, resolved)
                    finally:
                        provider.disconnect()
            except Exception:
                logger.exception("No se pudo resolver carpeta Graph mail_id=%s", mail_id)
                folder_path = "Carpeta de origen (nombre no disponible)"

        return {
            "id": row.id,
            "account_id": row.account_id,
            "user_id": row.user_id,
            "provider_message_id": row.provider_message_id,
            "folder_path": folder_path,
            "subject": row.subject,
            "from_address": row.from_address,
            "to_addresses": row.to_addresses,
            "cc_addresses": row.cc_addresses,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            "received_at": row.received_at.isoformat() if row.received_at else None,
            "has_attachments": row.has_attachments,
            "size_bytes": row.size_bytes,
            "content_sha256": row.content_sha256,
            "body_preview": row.body_preview,
            "body_text": body_text,
            "body_html": body_html or None,
            "body_is_html": bool(body_html),
            "attachment_names": row.attachment_names,
            "deleted_from_provider": row.deleted_from_provider,
            "restored_at": row.restored_at.isoformat() if row.restored_at else None,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "attachments": [
                {
                    "id": a.id,
                    "filename": a.filename,
                    "content_type": a.content_type,
                    "size_bytes": a.size_bytes,
                }
                for a in attachments
            ],
        }


class DownloadArchivedEmlUseCase:
    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        storage: MailStorage,
    ) -> None:
        self.archived_repo = archived_repo
        self.storage = storage

    def execute(self, *, tenant_id: int, user_id: int, role: UserRole, mail_id: str) -> tuple[bytes, str]:
        row = self.archived_repo.get(tenant_id, mail_id)
        if row is None:
            raise NotFoundError("Correo archivado no encontrado")
        if not _can_access_mail(role, user_id, row.user_id):
            raise AuthorizationError("No puede descargar este correo")
        try:
            data = self.storage.read_eml_from_dir(row.storage_path)
        except FileNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (row.subject or "mail")[:80])
        filename = f"{safe or 'mail'}.eml"
        return data, filename


class DownloadArchivedAttachmentUseCase:
    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        storage: MailStorage,
    ) -> None:
        self.archived_repo = archived_repo
        self.storage = storage

    def execute(
        self, *, tenant_id: int, user_id: int, role: UserRole, mail_id: str, attachment_id: int
    ) -> tuple[bytes, str, str]:
        row = self.archived_repo.get(tenant_id, mail_id)
        if row is None:
            raise NotFoundError("Correo archivado no encontrado")
        if not _can_access_mail(role, user_id, row.user_id):
            raise AuthorizationError("No puede descargar este adjunto")
        att = self.archived_repo.get_attachment(tenant_id, mail_id, attachment_id)
        if att is None:
            raise NotFoundError("Adjunto no encontrado")
        try:
            data = self.storage.read_attachment(att.storage_path)
        except FileNotFoundError as exc:
            raise NotFoundError("Archivo de adjunto no encontrado en storage") from exc
        return data, att.filename, att.content_type or "application/octet-stream"


class RestoreArchivedMailUseCase:
    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        account_repo: SqlAlchemyMailAccountRepository,
        factory: MailProviderFactory,
        cipher: CredentialCipher,
        storage: MailStorage,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.archived_repo = archived_repo
        self.account_repo = account_repo
        self.factory = factory
        self.cipher = cipher
        self.storage = storage
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        mail_id: str,
        folder_id: str | None = None,
        keep_copy: bool = False,
        target_account_id: int | None = None,
    ) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede restaurar")
        row = self.archived_repo.get(tenant_id, mail_id)
        if row is None:
            raise NotFoundError("Correo archivado no encontrado")
        if not _can_access_mail(role, user_id, row.user_id):
            raise AuthorizationError("No puede restaurar este correo")

        dest_id = int(target_account_id) if target_account_id else row.account_id
        cross_account = dest_id != row.account_id
        if cross_account:
            keep_copy = True

        account = self.account_repo.get(tenant_id, dest_id)
        if account is None:
            raise NotFoundError(
                "La cuenta destino no existe"
                if cross_account
                else "La cuenta original ya no existe; vinculá la cuenta nuevamente"
            )
        if not _can_restore_to_account(role, user_id, account):
            raise AuthorizationError("No puede restaurar a esa cuenta")
        if not account.credentials_encrypted:
            raise ValidationError("La cuenta destino no tiene credenciales; reconectala")

        try:
            eml = self.storage.read_eml_from_dir(row.storage_path)
        except FileNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc

        def _persist(tokens: dict[str, Any]) -> None:
            self.account_repo.update_credentials(tenant_id, account.id, self.cipher.encrypt_dict(tokens))

        provider = self.factory.create(
            provider=account.provider,
            config=account.config,
            credentials_encrypted=account.credentials_encrypted,
            on_tokens_refreshed=_persist if account.provider == "microsoft365" else None,
        )
        provider.connect()
        try:
            # Always restore into provider MailArchive folder (create if needed).
            # Optional folder_id only if caller explicitly overrides.
            result = provider.restore_message(eml, folder=folder_id)
            storage_path = row.storage_path
            self.audit_repo.add(
                tenant_id=tenant_id,
                user_id=user_id,
                action="mail.restored",
                resource_type="archived_mail",
                resource_id=mail_id,
                details={
                    "account_id": account.id,
                    "source_account_id": row.account_id,
                    "target_account_id": account.id,
                    "cross_account": cross_account,
                    "provider_message_id": result.provider_message_id,
                    "folder": result.folder,
                    "keep_copy": bool(keep_copy),
                    "removed_from_archive": not bool(keep_copy),
                },
            )
            if keep_copy:
                # Backup mode: leave EML + DB row; mark restored_at.
                self.archived_repo.mark_restored(tenant_id, mail_id)
                logger.info(
                    "Restored mail_id=%s keep_copy=true folder=%s target_account=%s cross=%s",
                    mail_id,
                    result.folder,
                    account.id,
                    cross_account,
                )
            else:
                deleted = self.archived_repo.delete_mail(tenant_id, mail_id)
                try:
                    _cleanup_mail_files(self.storage, deleted)
                    if deleted is None:
                        self.storage.delete_mail_dir(storage_path)
                except Exception:
                    logger.exception("No se pudo borrar storage de %s", storage_path)
            return {
                "id": mail_id,
                "provider_message_id": result.provider_message_id,
                "folder": result.folder,
                "account_id": account.id,
                "kept_in_archive": bool(keep_copy),
            }
        except Exception as exc:
            logger.exception("Restore failed mail_id=%s", mail_id)
            raise ValidationError(f"Error al restaurar: {exc}") from exc
        finally:
            provider.disconnect()


class BulkDownloadArchivedMailsUseCase:
    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        storage: MailStorage,
    ) -> None:
        self.archived_repo = archived_repo
        self.storage = storage

    def execute(
        self, *, tenant_id: int, user_id: int, role: UserRole, mail_ids: list[str]
    ) -> tuple[bytes, str]:
        import io
        import zipfile
        from datetime import datetime as dt

        if not mail_ids:
            raise ValidationError("No hay correos seleccionados")
        if len(mail_ids) > 500:
            raise ValidationError("Máximo 500 correos por descarga")

        buf = io.BytesIO()
        added = 0
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            used_names: set[str] = set()
            for mail_id in mail_ids:
                row = self.archived_repo.get(tenant_id, mail_id)
                if row is None or not _can_access_mail(role, user_id, row.user_id):
                    continue
                try:
                    data = self.storage.read_eml_from_dir(row.storage_path)
                except FileNotFoundError:
                    logger.warning("EML missing for bulk download %s", mail_id)
                    continue
                safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (row.subject or "mail")[:60])
                name = f"{safe or 'mail'}-{mail_id[:8]}.eml"
                if name in used_names:
                    name = f"{mail_id}.eml"
                used_names.add(name)
                zf.writestr(name, data)
                added += 1
        if added == 0:
            raise NotFoundError("No se pudo armar el ZIP (sin archivos accesibles)")
        stamp = dt.now().strftime("%Y%m%d-%H%M")
        return buf.getvalue(), f"archivados-{stamp}.zip"


class BulkRestoreArchivedMailsUseCase:
    def __init__(self, restore_uc: RestoreArchivedMailUseCase) -> None:
        self.restore_uc = restore_uc

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        mail_ids: list[str],
        keep_copy: bool = False,
        target_account_id: int | None = None,
    ) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede restaurar")
        if not mail_ids:
            raise ValidationError("No hay correos seleccionados")
        if len(mail_ids) > 200:
            raise ValidationError("Máximo 200 correos por restauración masiva")

        restored = 0
        failed: list[dict] = []
        for mail_id in mail_ids:
            try:
                self.restore_uc.execute(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=role,
                    mail_id=mail_id,
                    keep_copy=keep_copy,
                    target_account_id=target_account_id,
                )
                restored += 1
            except DomainError as exc:
                failed.append({"id": mail_id, "error": str(exc)})
            except Exception as exc:
                logger.exception("Bulk restore failed %s", mail_id)
                failed.append({"id": mail_id, "error": str(exc)})
        return {
            "restored": restored,
            "failed": failed,
            "requested": len(mail_ids),
            "kept_in_archive": bool(keep_copy) or bool(target_account_id),
        }


class DeleteArchivedMailUseCase:
    """Permanently remove from local archive and tombstone so jobs will not re-download."""

    def __init__(
        self,
        archived_repo: SqlAlchemyArchivedMailRepository,
        account_repo: SqlAlchemyMailAccountRepository,
        storage: MailStorage,
        audit_repo: IAuditLogRepository,
    ) -> None:
        self.archived_repo = archived_repo
        self.account_repo = account_repo
        self.storage = storage
        self.audit_repo = audit_repo

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        mail_id: str,
    ) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede eliminar del archivo")
        row = self.archived_repo.get(tenant_id, mail_id)
        if row is None:
            raise NotFoundError("Correo archivado no encontrado")
        if not _can_access_mail(role, user_id, row.user_id):
            raise AuthorizationError("No puede eliminar este correo")

        account = self.account_repo.get(tenant_id, row.account_id)
        provider_ids = [row.provider_message_id]
        if account is not None and account.provider == MailProviderType.IMAP.value:
            provider_ids = ImapProvider.message_id_aliases(
                row.provider_message_id, row.folder_path or None
            )

        for mid in provider_ids:
            self.archived_repo.add_exclusion(
                tenant_id=tenant_id,
                account_id=row.account_id,
                provider_message_id=mid,
                content_sha256=row.content_sha256,
                source_mail_id=mail_id,
                created_by=user_id,
            )

        deleted = self.archived_repo.delete_mail(tenant_id, mail_id)
        if deleted:
            try:
                _cleanup_mail_files(self.storage, deleted)
            except Exception:
                logger.exception("No se pudo borrar storage de %s", deleted.storage_path)

        self.audit_repo.add(
            tenant_id=tenant_id,
            user_id=user_id,
            action="mail.deleted_from_archive",
            resource_type="archived_mail",
            resource_id=mail_id,
            details={
                "account_id": row.account_id,
                "provider_message_id": row.provider_message_id,
                "content_sha256": row.content_sha256,
            },
        )
        logger.info(
            "Deleted from archive mail_id=%s account=%s provider_id=%s",
            mail_id,
            row.account_id,
            row.provider_message_id,
        )
        return {"id": mail_id, "deleted": True}


class BulkDeleteArchivedMailsUseCase:
    def __init__(self, delete_uc: DeleteArchivedMailUseCase) -> None:
        self.delete_uc = delete_uc

    def execute(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: UserRole,
        mail_ids: list[str],
    ) -> dict:
        if role == UserRole.READONLY:
            raise AuthorizationError("Rol solo lectura: no puede eliminar del archivo")
        if not mail_ids:
            raise ValidationError("No hay correos seleccionados")
        if len(mail_ids) > 200:
            raise ValidationError("Máximo 200 correos por eliminación masiva")

        deleted = 0
        failed: list[dict] = []
        for mail_id in mail_ids:
            try:
                self.delete_uc.execute(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=role,
                    mail_id=mail_id,
                )
                deleted += 1
            except DomainError as exc:
                failed.append({"id": mail_id, "error": str(exc)})
            except Exception as exc:
                logger.exception("Bulk delete from archive failed %s", mail_id)
                failed.append({"id": mail_id, "error": str(exc)})
        return {
            "requested": len(mail_ids),
            "deleted": deleted,
            "failed": failed,
        }
