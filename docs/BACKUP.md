# Backup and restore

MailArchive stores two kinds of data that must be backed up together:

1. **Database** — tenants, users, accounts, mail indexes, jobs, settings  
2. **Filesystem / object storage** — per-mail sidecars under `STORAGE_ROOT` (`{tenant_id}/{account_id}/yyyy/mm/{mail_id}/metadata.json`) and shared CAS blobs (`{tenant_id}/cas/eml/{sha256}`, `{tenant_id}/cas/att/{sha256}`). Legacy trees with `mail.eml` per message still work until optional CAS backfill.

Losing one without the other leaves an inconsistent archive.

## What to back up

| Item | Default (Docker SQLite) | Notes |
|------|-------------------------|--------|
| SQLite file | volume `mailarchive_data` → `/data/mailarchive.db` | Or `DATABASE_URL` / MySQL dump |
| Mail storage | volume `mailarchive_storage` → `/storage` | Entire tree |
| `.env` | host file | Secrets — keep offline, not in git |

## SQLite (Docker demo)

```bash
# Stop writes briefly for a consistent copy (optional but safer)
docker compose stop api

docker run --rm -v mailarchive-oss_mailarchive_data:/data -v "$PWD/backup:/out" alpine \
  cp /data/mailarchive.db /out/mailarchive-$(date +%F).db

docker run --rm -v mailarchive-oss_mailarchive_storage:/storage -v "$PWD/backup:/out" alpine \
  tar czf /out/storage-$(date +%F).tar.gz -C /storage .

docker compose start api
```

Volume names may differ (`docker volume ls | grep mailarchive`).

## MySQL

```bash
mysqldump -h HOST -u USER -p DATABASE > mailarchive-$(date +%F).sql
# plus tar of STORAGE_ROOT as above
```

## Restore (outline)

1. Stop the API.
2. Restore DB file/dump.
3. Extract storage tree to `STORAGE_ROOT`.
4. Restore `.env` (same Fernet/`DATA_ENCRYPTION_KEY` or encrypted credentials cannot be decrypted).
5. Start API; confirm `/health` and login.

## Upgrade notes

1. Read `CHANGELOG.md`.
2. Backup DB + storage.
3. `docker compose pull` / rebuild images.
4. Start API — Alembic runs on startup.
5. Smoke-test login, accounts list, **Jobs** (`/app/jobs`), and one archived mail download.
6. **v1.1.0:** Alembic `0007_content_cas` adds `content_blobs` + `rfc_message_id`. Optional: run `backfill_content_cas` to move legacy EML files into CAS (not required for the app to start).

## Encryption caveat

OAuth tokens and IMAP passwords are encrypted at rest with `DATA_ENCRYPTION_KEY`.  
If you rotate that key without re-encrypting credentials, linked accounts will fail until re-linked.
