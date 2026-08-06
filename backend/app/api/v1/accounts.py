"""Mail accounts endpoints — IMAP + Microsoft OAuth."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps.auth import CurrentUserContext, get_current_user, map_domain_error
from app.application.use_cases.accounts.account_use_cases import (
    CompleteMicrosoftOAuthUseCase,
    CreateImapAccountUseCase,
    DeleteAccountUseCase,
    ListAccountFoldersUseCase,
    ListAccountMessagesUseCase,
    ListAccountsUseCase,
    OAuthStateService,
    PreviewProviderMessageUseCase,
    StartMicrosoftOAuthUseCase,
    TestAccountConnectionUseCase,
    TestImapConnectionUseCase,
)
from app.config import Settings, get_settings
from app.domain.exceptions import DomainError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyMailAccountRepository
from app.infrastructure.persistence.repositories.sqlalchemy_repos import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.providers.factory import MailProviderFactory
from app.infrastructure.security.fernet_cipher import CredentialCipher
from app.schemas.accounts import (
    AccountPublic,
    ConnectionTestResponse,
    FolderPublic,
    ImapCreateRequest,
    ImapTestRequest,
    OAuthStartResponse,
    ProviderMessageDetail,
    ProviderMessagePublic,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/accounts", tags=["accounts"])


def _cipher(settings: Settings) -> CredentialCipher:
    return CredentialCipher(settings)


@router.get("", response_model=list[AccountPublic])
def list_accounts(
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> list[AccountPublic]:
    uc = ListAccountsUseCase(
        SqlAlchemyMailAccountRepository(db),
        SqlAlchemyUserRepository(db),
    )
    items = uc.execute(tenant_id=ctx.user.tenant_id, user_id=ctx.user.id, role=ctx.user.role)
    return [AccountPublic(**i) for i in items]


@router.post("/imap/test", response_model=ConnectionTestResponse)
def test_imap(body: ImapTestRequest, ctx: Annotated[CurrentUserContext, Depends(get_current_user)]) -> ConnectionTestResponse:
    _ = ctx
    result = TestImapConnectionUseCase().execute(
        host=body.host,
        port=body.port,
        ssl=body.ssl,
        username=body.username,
        password=body.password,
    )
    return ConnectionTestResponse(**result)


@router.post("/imap", response_model=dict)
def create_imap(
    body: ImapCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    uc = CreateImapAccountUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        cipher=_cipher(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        return uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            host=body.host,
            port=body.port,
            ssl=body.ssl,
            username=body.username,
            password=body.password,
            email=str(body.email) if body.email else None,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc


@router.get("/microsoft/oauth/start", response_model=OAuthStartResponse)
def microsoft_oauth_start(
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthStartResponse:
    uc = StartMicrosoftOAuthUseCase(settings, OAuthStateService(settings))
    try:
        result = uc.execute(tenant_id=ctx.user.tenant_id, user_id=ctx.user.id)
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return OAuthStartResponse(authorize_url=result["authorize_url"])


@router.get("/microsoft/oauth/callback")
def microsoft_oauth_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    frontend = settings.app_url.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/app/accounts?error={error}")
    if not code or not state:
        return RedirectResponse(f"{frontend}/app/accounts?error=missing_code")
    uc = CompleteMicrosoftOAuthUseCase(
        settings=settings,
        state_service=OAuthStateService(settings),
        account_repo=SqlAlchemyMailAccountRepository(db),
        cipher=_cipher(settings),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        result = uc.execute(code=code, state=state)
        return RedirectResponse(
            f"{frontend}/app/accounts?linked=1&email={result['email']}&account_id={result['account_id']}"
        )
    except DomainError as exc:
        logger.warning("Microsoft OAuth domain error: %s", exc)
        return RedirectResponse(f"{frontend}/app/accounts?error={quote(str(exc), safe='')}")
    except Exception as exc:
        logger.exception("Microsoft OAuth callback failed")
        # Surface a short safe hint (no secrets); full detail stays in API logs
        hint = quote(str(exc)[:180], safe="")
        return RedirectResponse(f"{frontend}/app/accounts?error={hint or 'oauth_failed'}")


@router.post("/{account_id}/test", response_model=ConnectionTestResponse)
def test_account(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectionTestResponse:
    cipher = _cipher(settings)
    uc = TestAccountConnectionUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
    )
    try:
        result = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ConnectionTestResponse(**result)


@router.get("/{account_id}/folders", response_model=list[FolderPublic])
def list_folders(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[FolderPublic]:
    cipher = _cipher(settings)
    uc = ListAccountFoldersUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
    )
    try:
        items = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return [FolderPublic(**i) for i in items]


@router.get("/{account_id}/messages", response_model=list[ProviderMessagePublic])
def list_messages(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    folder_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    only_with_attachments: bool = False,
) -> list[ProviderMessagePublic]:
    cipher = _cipher(settings)
    uc = ListAccountMessagesUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
    )
    try:
        items = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
            folder_id=folder_id,
            limit=limit,
            only_with_attachments=only_with_attachments,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return [ProviderMessagePublic(**i) for i in items]


@router.get("/{account_id}/messages/{message_id}", response_model=ProviderMessageDetail)
def preview_message(
    account_id: int,
    message_id: str,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    folder_id: str | None = None,
) -> ProviderMessageDetail:
    cipher = _cipher(settings)
    uc = PreviewProviderMessageUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
    )
    try:
        item = uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
            message_id=message_id,
            folder_id=folder_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return ProviderMessageDetail(**item)


@router.get("/{account_id}/messages/{message_id}/attachments/{attachment_id}/download")
def download_provider_attachment(
    account_id: int,
    message_id: str,
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    folder_id: str | None = None,
) -> Response:
    cipher = _cipher(settings)
    uc = PreviewProviderMessageUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        factory=MailProviderFactory(settings, cipher),
        cipher=cipher,
    )
    try:
        item = uc.download_attachment(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
            message_id=message_id,
            attachment_id=attachment_id,
            folder_id=folder_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    filename = item["filename"] or f"adjunto-{attachment_id}"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
    }
    return Response(
        content=item["content"],
        media_type=item.get("content_type") or "application/octet-stream",
        headers=headers,
    )


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    ctx: Annotated[CurrentUserContext, Depends(get_current_user)],
) -> dict:
    uc = DeleteAccountUseCase(
        account_repo=SqlAlchemyMailAccountRepository(db),
        audit_repo=SqlAlchemyAuditLogRepository(db),
    )
    try:
        uc.execute(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            role=ctx.user.role,
            account_id=account_id,
        )
    except DomainError as exc:
        raise map_domain_error(exc) from exc
    return {"message": "Cuenta eliminada"}
