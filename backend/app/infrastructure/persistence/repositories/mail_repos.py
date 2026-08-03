"""Mail account and archived mail repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.enums.providers import AccountStatus, MailProviderType
from app.infrastructure.persistence.models import ArchivedMailModel, AttachmentModel, MailAccountModel


@dataclass
class MailAccount:
    id: int
    tenant_id: int
    user_id: int
    provider: str
    email: str
    display_name: str | None
    status: str
    config: dict | None
    credentials_encrypted: str | None
    linked_at: datetime
    last_sync_at: datetime | None
    last_error: str | None


def _to_account(row: MailAccountModel) -> MailAccount:
    return MailAccount(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        provider=row.provider,
        email=row.email,
        display_name=row.display_name,
        status=row.status,
        config=row.config,
        credentials_encrypted=row.credentials_encrypted,
        linked_at=row.linked_at,
        last_sync_at=row.last_sync_at,
        last_error=row.last_error,
    )


class SqlAlchemyMailAccountRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, tenant_id: int, user_id: int) -> list[MailAccount]:
        rows = self._db.scalars(
            select(MailAccountModel)
            .where(MailAccountModel.tenant_id == tenant_id, MailAccountModel.user_id == user_id)
            .order_by(MailAccountModel.id.desc())
        ).all()
        return [_to_account(r) for r in rows]

    def list_for_tenant(self, tenant_id: int) -> list[MailAccount]:
        rows = self._db.scalars(
            select(MailAccountModel)
            .where(MailAccountModel.tenant_id == tenant_id)
            .order_by(MailAccountModel.id.desc())
        ).all()
        return [_to_account(r) for r in rows]

    def get(self, tenant_id: int, account_id: int) -> MailAccount | None:
        row = self._db.scalar(
            select(MailAccountModel).where(
                MailAccountModel.tenant_id == tenant_id, MailAccountModel.id == account_id
            )
        )
        return _to_account(row) if row else None

    def upsert_microsoft(
        self,
        *,
        tenant_id: int,
        user_id: int,
        email: str,
        display_name: str | None,
        credentials_encrypted: str,
        config: dict | None = None,
    ) -> MailAccount:
        row = self._db.scalar(
            select(MailAccountModel).where(
                MailAccountModel.tenant_id == tenant_id,
                MailAccountModel.user_id == user_id,
                MailAccountModel.email == email.lower(),
                MailAccountModel.provider == MailProviderType.MICROSOFT365.value,
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = MailAccountModel(
                tenant_id=tenant_id,
                user_id=user_id,
                provider=MailProviderType.MICROSOFT365.value,
                email=email.lower(),
                display_name=display_name,
                status=AccountStatus.CONNECTED.value,
                config=config or {},
                credentials_encrypted=credentials_encrypted,
                linked_at=now,
                last_sync_at=now,
                last_error=None,
            )
            self._db.add(row)
        else:
            row.display_name = display_name
            row.status = AccountStatus.CONNECTED.value
            row.credentials_encrypted = credentials_encrypted
            row.config = config or row.config or {}
            row.last_sync_at = now
            row.last_error = None
        self._db.flush()
        return _to_account(row)

    def create_imap(
        self,
        *,
        tenant_id: int,
        user_id: int,
        email: str,
        config: dict,
        credentials_encrypted: str,
        status: str,
        last_error: str | None = None,
    ) -> MailAccount:
        row = MailAccountModel(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=MailProviderType.IMAP.value,
            email=email.lower(),
            display_name=email,
            status=status,
            config=config,
            credentials_encrypted=credentials_encrypted,
            last_error=last_error,
        )
        self._db.add(row)
        self._db.flush()
        return _to_account(row)

    def update_credentials(self, tenant_id: int, account_id: int, credentials_encrypted: str) -> None:
        row = self._db.scalar(
            select(MailAccountModel).where(
                MailAccountModel.tenant_id == tenant_id, MailAccountModel.id == account_id
            )
        )
        if row:
            row.credentials_encrypted = credentials_encrypted
            row.last_sync_at = datetime.now(UTC)
            row.status = AccountStatus.CONNECTED.value
            row.last_error = None
            self._db.flush()

    def set_status(self, tenant_id: int, account_id: int, status: str, error: str | None = None) -> None:
        row = self._db.scalar(
            select(MailAccountModel).where(
                MailAccountModel.tenant_id == tenant_id, MailAccountModel.id == account_id
            )
        )
        if row:
            row.status = status
            row.last_error = error
            self._db.flush()

    def delete(self, tenant_id: int, account_id: int) -> bool:
        row = self._db.scalar(
            select(MailAccountModel).where(
                MailAccountModel.tenant_id == tenant_id, MailAccountModel.id == account_id
            )
        )
        if not row:
            return False
        self._db.delete(row)
        self._db.flush()
        return True


class SqlAlchemyArchivedMailRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        mail_id: str,
        tenant_id: int,
        account_id: int,
        user_id: int,
        provider_message_id: str,
        folder_path: str,
        subject: str,
        from_address: str,
        to_addresses: str,
        cc_addresses: str,
        sent_at: datetime | None,
        received_at: datetime | None,
        has_attachments: bool,
        size_bytes: int,
        content_sha256: str,
        storage_path: str,
        body_preview: str | None,
        body_text: str | None,
        attachment_names: str | None,
        deleted_from_provider: bool,
        attachments: list[dict[str, Any]],
    ) -> ArchivedMailModel:
        row = ArchivedMailModel(
            id=mail_id,
            tenant_id=tenant_id,
            account_id=account_id,
            user_id=user_id,
            provider_message_id=provider_message_id,
            folder_path=folder_path,
            subject=subject,
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            sent_at=sent_at,
            received_at=received_at,
            has_attachments=has_attachments,
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            storage_path=storage_path,
            body_preview=body_preview,
            body_text=body_text,
            attachment_names=attachment_names,
            deleted_from_provider=deleted_from_provider,
        )
        self._db.add(row)
        self._db.flush()
        for att in attachments:
            self._db.add(
                AttachmentModel(
                    tenant_id=tenant_id,
                    archived_mail_id=mail_id,
                    filename=att["filename"],
                    content_type=att["content_type"],
                    size_bytes=att["size_bytes"],
                    sha256=att["sha256"],
                    storage_path=att["storage_path"],
                )
            )
        self._db.flush()
        return row

    def get_by_provider_message_id(
        self, tenant_id: int, account_id: int, provider_message_id: str
    ) -> ArchivedMailModel | None:
        return self._db.scalar(
            select(ArchivedMailModel).where(
                ArchivedMailModel.tenant_id == tenant_id,
                ArchivedMailModel.account_id == account_id,
                ArchivedMailModel.provider_message_id == provider_message_id,
            )
        )

    def get(self, tenant_id: int, mail_id: str) -> ArchivedMailModel | None:
        return self._db.scalar(
            select(ArchivedMailModel).where(
                ArchivedMailModel.tenant_id == tenant_id, ArchivedMailModel.id == mail_id
            )
        )

    def list_attachments(self, tenant_id: int, mail_id: str) -> list[AttachmentModel]:
        return list(
            self._db.scalars(
                select(AttachmentModel).where(
                    AttachmentModel.tenant_id == tenant_id,
                    AttachmentModel.archived_mail_id == mail_id,
                )
            ).all()
        )

    def get_attachment(self, tenant_id: int, mail_id: str, attachment_id: int) -> AttachmentModel | None:
        return self._db.scalar(
            select(AttachmentModel).where(
                AttachmentModel.tenant_id == tenant_id,
                AttachmentModel.archived_mail_id == mail_id,
                AttachmentModel.id == attachment_id,
            )
        )

    def update_folder_path(self, tenant_id: int, mail_id: str, folder_path: str) -> None:
        row = self.get(tenant_id, mail_id)
        if row:
            row.folder_path = folder_path
            self._db.flush()

    def delete_mail(self, tenant_id: int, mail_id: str) -> str | None:
        """Delete archived mail + attachments. Returns storage_path if deleted."""
        row = self.get(tenant_id, mail_id)
        if row is None:
            return None
        storage_path = row.storage_path
        atts = self.list_attachments(tenant_id, mail_id)
        for att in atts:
            self._db.delete(att)
        self._db.delete(row)
        self._db.flush()
        return storage_path

    def search(
        self,
        tenant_id: int,
        *,
        user_id: int | None = None,
        q: str | None = None,
        account_id: int | None = None,
        from_address: str | None = None,
        has_attachments: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ArchivedMailModel], int]:
        from sqlalchemy import func

        filters = [ArchivedMailModel.tenant_id == tenant_id]
        if user_id is not None:
            filters.append(ArchivedMailModel.user_id == user_id)
        if account_id is not None:
            filters.append(ArchivedMailModel.account_id == account_id)
        if from_address:
            filters.append(ArchivedMailModel.from_address.ilike(f"%{from_address}%"))
        if has_attachments is not None:
            filters.append(ArchivedMailModel.has_attachments.is_(has_attachments))
        if date_from is not None:
            filters.append(ArchivedMailModel.sent_at >= date_from)
        if date_to is not None:
            filters.append(ArchivedMailModel.sent_at <= date_to)
        if q:
            like = f"%{q}%"
            filters.append(
                or_(
                    ArchivedMailModel.subject.ilike(like),
                    ArchivedMailModel.from_address.ilike(like),
                    ArchivedMailModel.to_addresses.ilike(like),
                    ArchivedMailModel.cc_addresses.ilike(like),
                    ArchivedMailModel.body_preview.ilike(like),
                    ArchivedMailModel.body_text.ilike(like),
                    ArchivedMailModel.attachment_names.ilike(like),
                )
            )

        total = int(self._db.scalar(select(func.count()).select_from(ArchivedMailModel).where(*filters)) or 0)
        stmt = (
            select(ArchivedMailModel)
            .where(*filters)
            .order_by(ArchivedMailModel.archived_at.desc())
            .offset(max(0, offset))
            .limit(limit)
        )
        return list(self._db.scalars(stmt).all()), total

    def search_ids(
        self,
        tenant_id: int,
        *,
        user_id: int | None = None,
        q: str | None = None,
        account_id: int | None = None,
        from_address: str | None = None,
        has_attachments: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 2000,
    ) -> tuple[list[str], int]:
        from sqlalchemy import func

        filters = [ArchivedMailModel.tenant_id == tenant_id]
        if user_id is not None:
            filters.append(ArchivedMailModel.user_id == user_id)
        if account_id is not None:
            filters.append(ArchivedMailModel.account_id == account_id)
        if from_address:
            filters.append(ArchivedMailModel.from_address.ilike(f"%{from_address}%"))
        if has_attachments is not None:
            filters.append(ArchivedMailModel.has_attachments.is_(has_attachments))
        if date_from is not None:
            filters.append(ArchivedMailModel.sent_at >= date_from)
        if date_to is not None:
            filters.append(ArchivedMailModel.sent_at <= date_to)
        if q:
            like = f"%{q}%"
            filters.append(
                or_(
                    ArchivedMailModel.subject.ilike(like),
                    ArchivedMailModel.from_address.ilike(like),
                    ArchivedMailModel.to_addresses.ilike(like),
                    ArchivedMailModel.cc_addresses.ilike(like),
                    ArchivedMailModel.body_preview.ilike(like),
                    ArchivedMailModel.body_text.ilike(like),
                    ArchivedMailModel.attachment_names.ilike(like),
                )
            )
        total = int(self._db.scalar(select(func.count()).select_from(ArchivedMailModel).where(*filters)) or 0)
        ids = list(
            self._db.scalars(
                select(ArchivedMailModel.id)
                .where(*filters)
                .order_by(ArchivedMailModel.archived_at.desc())
                .limit(limit)
            ).all()
        )
        return [str(i) for i in ids], total
