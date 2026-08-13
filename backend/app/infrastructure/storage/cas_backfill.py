"""One-shot backfill: move legacy EML/attachments into CAS and fill rfc_message_id."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import ArchivedMailModel, AttachmentModel, ContentBlobModel
from app.infrastructure.persistence.repositories.mail_repos import SqlAlchemyArchivedMailRepository
from app.infrastructure.storage.cas import (
    cas_att_key,
    cas_eml_key,
    identity_matches,
    is_cas_path,
    rfc_message_id_from_eml,
)
from app.domain.interfaces.mail_storage import MailStorage, StoredAttachment

logger = logging.getLogger(__name__)


def backfill_content_cas(
    db: Session,
    storage: MailStorage,
    *,
    tenant_id: int | None = None,
    limit: int | None = None,
    remove_legacy_files: bool = True,
) -> dict:
    """Promote existing archive rows to CAS. Safe to re-run."""
    stmt = select(ArchivedMailModel).order_by(ArchivedMailModel.archived_at.asc())
    if tenant_id is not None:
        stmt = stmt.where(ArchivedMailModel.tenant_id == tenant_id)
    rows = list(db.scalars(stmt).all())
    if limit is not None:
        rows = rows[:limit]

    repo = SqlAlchemyArchivedMailRepository(db)
    promoted = 0
    rfc_filled = 0
    shared = 0
    errors = 0
    donors: dict[str, ArchivedMailModel] = {}

    for row in rows:
        try:
            eml = storage.read_eml_from_dir(row.storage_path)
        except FileNotFoundError:
            logger.warning("Backfill skip missing EML mail_id=%s path=%s", row.id, row.storage_path)
            errors += 1
            continue

        rfc_id = rfc_message_id_from_eml(eml)
        if rfc_id and row.rfc_message_id != rfc_id:
            row.rfc_message_id = rfc_id
            rfc_filled += 1

        eml_sha = row.content_sha256 or hashlib.sha256(eml).hexdigest()
        eml_key = cas_eml_key(row.tenant_id, eml_sha)
        legacy_eml = None
        if hasattr(storage, "root"):
            candidate = Path(storage.root) / row.storage_path / "mail.eml"
            if candidate.is_file():
                legacy_eml = candidate
        if legacy_eml is not None:
            storage.put_blob_from_path(eml_key, str(legacy_eml), "message/rfc822")
        else:
            storage.put_blob_if_absent(eml_key, eml, "message/rfc822")
        if row.content_sha256 != eml_sha:
            row.content_sha256 = eml_sha

        att_models = list(
            db.scalars(
                select(AttachmentModel).where(
                    AttachmentModel.tenant_id == row.tenant_id,
                    AttachmentModel.archived_mail_id == row.id,
                )
            ).all()
        )
        stored_atts: list[StoredAttachment] = []
        for att in att_models:
            try:
                data = storage.read_attachment(att.storage_path)
            except FileNotFoundError:
                logger.warning("Backfill missing att mail=%s att=%s", row.id, att.id)
                continue
            sha = att.sha256 or hashlib.sha256(data).hexdigest()
            key = cas_att_key(row.tenant_id, sha)
            legacy_att = None
            if hasattr(storage, "root") and att.storage_path and not is_cas_path(att.storage_path):
                candidate = Path(storage.root) / att.storage_path
                if candidate.is_file():
                    legacy_att = candidate
            if legacy_att is not None:
                storage.put_blob_from_path(key, str(legacy_att), att.content_type or "application/octet-stream")
            else:
                storage.put_blob_if_absent(key, data, att.content_type or "application/octet-stream")
            if att.storage_path != key:
                att.storage_path = key
            if att.sha256 != sha:
                att.sha256 = sha
            stored_atts.append(
                StoredAttachment(
                    filename=att.filename,
                    content_type=att.content_type,
                    size_bytes=att.size_bytes,
                    sha256=sha,
                    relative_path=key,
                )
            )

        if rfc_id and rfc_id in donors:
            donor = donors[rfc_id]
            if donor.account_id != row.account_id and identity_matches(
                donor_from=donor.from_address,
                donor_subject=donor.subject,
                donor_sent_at=donor.sent_at,
                from_address=row.from_address,
                subject=row.subject,
                sent_at=row.sent_at,
            ):
                row.content_sha256 = donor.content_sha256
                eml_sha = donor.content_sha256
                shared += 1
        elif rfc_id:
            donors[rfc_id] = row

        extra = {
            "provider_message_id": row.provider_message_id,
            "subject": row.subject,
            "from": row.from_address,
            "size_bytes": row.size_bytes,
            "rfc_message_id": row.rfc_message_id,
        }
        sidecar_dir = Path(storage.root) / row.storage_path if hasattr(storage, "root") else None
        if sidecar_dir is not None:
            sidecar_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "mail_id": row.id,
                "content_sha256": eml_sha,
                "eml_cas_path": cas_eml_key(row.tenant_id, eml_sha),
                "cas": True,
                "attachments": [
                    {
                        "filename": a.filename,
                        "content_type": a.content_type,
                        "size_bytes": a.size_bytes,
                        "sha256": a.sha256,
                        "path": a.relative_path,
                    }
                    for a in stored_atts
                ],
                **extra,
            }
            (sidecar_dir / "metadata.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if remove_legacy_files:
                legacy_eml = sidecar_dir / "mail.eml"
                if legacy_eml.is_file():
                    legacy_eml.unlink()
                adj = sidecar_dir / "adjuntos"
                if adj.is_dir():
                    import shutil

                    shutil.rmtree(adj, ignore_errors=True)

        promoted += 1
        if promoted % 200 == 0:
            db.flush()
            logger.info("CAS backfill progress promoted=%s rfc=%s shared=%s", promoted, rfc_filled, shared)

    db.flush()
    _rebuild_blob_refcounts(db, repo)
    db.commit()
    orphans_removed = _delete_orphan_cas_files(storage, db)
    logger.info(
        "CAS backfill done promoted=%s rfc_filled=%s shared_eml=%s errors=%s orphans_removed=%s",
        promoted,
        rfc_filled,
        shared,
        errors,
        orphans_removed,
    )
    return {
        "promoted": promoted,
        "rfc_filled": rfc_filled,
        "shared_eml": shared,
        "errors": errors,
        "orphans_removed": orphans_removed,
        "total": len(rows),
    }


def _rebuild_blob_refcounts(db: Session, repo: SqlAlchemyArchivedMailRepository) -> None:
    db.execute(delete(ContentBlobModel))
    db.flush()
    mails = list(db.scalars(select(ArchivedMailModel)).all())
    for row in mails:
        if not row.content_sha256:
            continue
        repo.add_blob_ref(
            tenant_id=row.tenant_id,
            sha256=row.content_sha256,
            kind="eml",
            size_bytes=int(row.size_bytes or 0),
            storage_path=cas_eml_key(row.tenant_id, row.content_sha256),
        )
        atts = list(
            db.scalars(
                select(AttachmentModel).where(
                    AttachmentModel.tenant_id == row.tenant_id,
                    AttachmentModel.archived_mail_id == row.id,
                )
            ).all()
        )
        for att in atts:
            if not att.sha256:
                continue
            path = att.storage_path if is_cas_path(att.storage_path) else cas_att_key(row.tenant_id, att.sha256)
            repo.add_blob_ref(
                tenant_id=row.tenant_id,
                sha256=att.sha256,
                kind="att",
                size_bytes=int(att.size_bytes or 0),
                storage_path=path,
            )
    db.flush()


def _delete_orphan_cas_files(storage: MailStorage, db: Session) -> int:
    """Remove CAS files not referenced by content_blobs (filesystem only)."""
    if not hasattr(storage, "root"):
        return 0
    keep = {row[0] for row in db.execute(select(ContentBlobModel.sha256)).all()}
    removed = 0
    root = Path(storage.root)
    for kind in ("eml", "att"):
        folder = root / "1" / "cas" / kind
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.name.endswith(".tmp"):
                continue
            if path.name in keep:
                continue
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                continue
    return removed
