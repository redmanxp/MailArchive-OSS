"""Archive and search endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user, map_domain_error
from app.application.use_cases.accounts.account_use_cases import (
    ArchiveSingleMessageUseCase,
    BulkDeleteArchivedMailsUseCase,
    BulkDownloadArchivedMailsUseCase,
    BulkRestoreArchivedMailsUseCase,
    DeleteArchivedMailUseCase,
    DownloadArchivedAttachmentUseCase,
    DownloadArchivedEmlUseCase,
    GetArchivedMailUseCase,
    RestoreArchivedMailUseCase,
    SearchArchivedMailsUseCase,
)
from app.config import Settings, get_settings
from app.domain.exceptions import DomainError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.mail_repos import (
    SqlAlchemyArchivedMailRepository,
    SqlAlchemyMailAccountRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_repos import SqlAlchemyAuditLogRepository
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.infrastructure.storage.factory import build_mail_storage
from app.schemas.accounts import (
    ArchiveMessageRequest,
    ArchiveMessageResponse,
    ArchivedMailDetail,
    ArchivedMailIdsResponse,
    ArchivedMailPublic,
    ArchivedMailSearchResponse,
    BulkDeleteFromArchiveResponse,
    BulkMailIdsRequest,
    BulkRestoreResponse,
    DeleteFromArchiveResponse,
    RestoreMailRequest,
    RestoreMailResponse,
)

archive_router = APIRouter(prefix="/archive", tags=["archive"])
mails_router = APIRouter(prefix="/mails", tags=["mails"])


@archive_router.post("/messages", response_model=ArchiveMessageResponse)
def archive_message(
    body: ArchiveMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArchiveMessageResponse:
    cipher = CredentialCipher(settings)
    uc = ArchiveSingleMessageUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
        storage=build_mail_storage(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=body.account_id,
            message_id=body.message_id,
            folder_id=body.folder_id,
            folder_path=body.folder_path,
            delete_after_archive=body.delete_after_archive,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ArchiveMessageResponse(**result)


@mails_router.get("/search", response_model=ArchivedMailSearchResponse)
def search_mails(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    q: str | None = None,
    account_id: int | None = None,
    from_address: str | None = None,
    has_attachments: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ArchivedMailSearchResponse:
    uc = SearchArchivedMailsUseCase(SqlAlchemyArchivedMailRepository(db))
    result = uc.execute(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        role=ctx.user.role,
        q=q,
        account_id=account_id,
        from_address=from_address,
        has_attachments=has_attachments,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return ArchivedMailSearchResponse(
        items=[ArchivedMailPublic(**i) for i in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@mails_router.get("/search/ids", response_model=ArchivedMailIdsResponse)
def search_mail_ids(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    q: str | None = None,
    account_id: int | None = None,
    from_address: str | None = None,
    has_attachments: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=2000, ge=1, le=2000),
) -> ArchivedMailIdsResponse:
    uc = SearchArchivedMailsUseCase(SqlAlchemyArchivedMailRepository(db))
    result = uc.search_ids(
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        role=ctx.user.role,
        q=q,
        account_id=account_id,
        from_address=from_address,
        has_attachments=has_attachments,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return ArchivedMailIdsResponse(**result)


@mails_router.post("/bulk/download")
def bulk_download_mails(
    body: BulkMailIdsRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    uc = BulkDownloadArchivedMailsUseCase(
        SqlAlchemyArchivedMailRepository(db),
        build_mail_storage(settings),
    )
    try:
        data, filename = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_ids=body.mail_ids,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


@mails_router.post("/bulk/restore", response_model=BulkRestoreResponse)
def bulk_restore_mails(
    body: BulkMailIdsRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BulkRestoreResponse:
    cipher = CredentialCipher(settings)
    restore_uc = RestoreArchivedMailUseCase(
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
        storage=build_mail_storage(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    uc = BulkRestoreArchivedMailsUseCase(restore_uc)
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_ids=body.mail_ids,
            keep_copy=bool(body.keep_copy),
            target_account_id=body.target_account_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return BulkRestoreResponse(**result)


@mails_router.post("/bulk/delete", response_model=BulkDeleteFromArchiveResponse)
def bulk_delete_mails_from_archive(
    body: BulkMailIdsRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BulkDeleteFromArchiveResponse:
    delete_uc = DeleteArchivedMailUseCase(
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        storage=build_mail_storage(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    uc = BulkDeleteArchivedMailsUseCase(delete_uc)
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_ids=body.mail_ids,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return BulkDeleteFromArchiveResponse(**result)


@mails_router.get("/{mail_id}", response_model=ArchivedMailDetail)
def get_mail(
    mail_id: str,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArchivedMailDetail:
    uc = GetArchivedMailUseCase(
        SqlAlchemyArchivedMailRepository(db),
        build_mail_storage(settings),
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, CredentialCipher(settings)),
        cipher=CredentialCipher(settings),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_id=mail_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ArchivedMailDetail(**result)


@mails_router.get("/{mail_id}/download")
def download_eml(
    mail_id: str,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    uc = DownloadArchivedEmlUseCase(
        SqlAlchemyArchivedMailRepository(db),
        build_mail_storage(settings),
    )
    try:
        data, filename = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_id=mail_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type="message/rfc822",
        headers={"Content-Disposition": disposition},
    )


@mails_router.get("/{mail_id}/attachments/{attachment_id}/download")
def download_attachment(
    mail_id: str,
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    uc = DownloadArchivedAttachmentUseCase(
        SqlAlchemyArchivedMailRepository(db),
        build_mail_storage(settings),
    )
    try:
        data, filename, content_type = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_id=mail_id,
            attachment_id=attachment_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )


@mails_router.post("/{mail_id}/restore", response_model=RestoreMailResponse)
def restore_mail(
    mail_id: str,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: RestoreMailRequest | None = None,
) -> RestoreMailResponse:
    cipher = CredentialCipher(settings)
    uc = RestoreArchivedMailUseCase(
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
        storage=build_mail_storage(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_id=mail_id,
            folder_id=(body.folder_id if body else None),
            keep_copy=bool(body.keep_copy) if body else False,
            target_account_id=(body.target_account_id if body else None),
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return RestoreMailResponse(**result)


@mails_router.delete("/{mail_id}", response_model=DeleteFromArchiveResponse)
def delete_mail_from_archive(
    mail_id: str,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeleteFromArchiveResponse:
    uc = DeleteArchivedMailUseCase(
        archived_repo=SqlAlchemyArchivedMailRepository(db),
        account_repo=SqlAlchemyMailAccountRepository(db),
        storage=build_mail_storage(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            mail_id=mail_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return DeleteFromArchiveResponse(**result)
