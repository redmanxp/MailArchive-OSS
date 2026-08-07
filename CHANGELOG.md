# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-08-07

### Added

- Delete from archive (single + bulk) with confirmation
- Tombstone table `archived_mail_exclusions` so scheduled jobs do not re-download excluded messages

### Fixed

- SQLite foreign-key error when deleting archived mails that have attachments
- Purge / hard-delete account also clears related exclusions

## [1.0.0] - 2026-08-06

First stable public release.

### Highlights

- **Microsoft 365** archive / restore (Graph OAuth)
- **IMAP** archive / restore (incl. Gmail via App Password preset)
- **Local EML storage** (filesystem or S3-compatible) — no PST lock-in
- **Full-text search** over the archive
- **RBAC** (admin / supervisor / user / read-only) + audit trail
- Scheduled incremental archive, employee departure, account transfer/unlink
- Docker Compose + **GHCR** pre-built images

### Changed

- README / TODO: product framing as self-hosted corporate archive; roadmap v1.1 = scheduled incremental archive (not “sync”); Gmail OAuth deferred; export EML called out
- README / TODO: employee departure, transfer linked accounts, unlink/deactivate flows (keep archive by default)
- Screenshot capture redacts emails **and** SMTP/IMAP hostnames to `*.example.com`
- Archived mails list: show **Account** column (email of linked mailbox)
- Refresh README screenshots (login, dashboard, users, settings, archive, accounts)
- User manuals ES/EN aligned with current product (S3, keep_copy, tenant mode, setup_url, Settings sections)

### Fixed

- S3 endpoint URLs: strip whitespace (trailing space broke MinIO/boto URI validation)
- Admin invite/reset: return copyable `setup_url` when email fails; UI shows warning (no silent success redirect)
- SMTP test crashed with Internal Server Error: password decrypt used a dict instead of the Fernet token
- Microsoft OAuth callback now logs and surfaces token-exchange errors instead of opaque `oauth_failed`
- Reject Azure **Secret ID** (GUID) when saving Microsoft client secret; hint clarifies to paste **Value**
- Strip accidental spaces from Microsoft redirect URI on save
- SQLite `database is locked` under concurrent archive jobs (WAL + short transactions + retries)
- Single-message archive is idempotent when the mail is already in the archive
- UI datetimes treat naive API timestamps as UTC and display in the browser local zone

### Added

- **Employee departure** wizard: `GET/POST /api/v1/admin/users/{id}/departure` + UI `/app/users/:id/departure`
- Users / Accounts list filters (client-side search + role / provider)
- Standalone `docker-compose.prod.yml` for GHCR pre-built install (no local build)
- Retry failed/cancelled archive jobs (`POST /archive/jobs/{id}/retry`); dashboard archive health
- Job detail modal; schedule run-now + active schedule indicator
- Gmail IMAP UI preset (`imap.gmail.com:993` + App Password hint)
- **Scheduled incremental archive** per account (`archive_schedules`, poller, Cuentas → clock icon)
- Admin **transfer** linked mail account; soft-**unlink** (keeps archive)
- Deactivate user: unlink accounts or transfer
- Restore optional **keep copy in app** (`keep_copy`)
- S3-compatible mail storage (`STORAGE_BACKEND=s3`); filesystem remains default
- Tenant mode `single` / `multi`
- Dependabot; install wizard (SQLite/MySQL + storage folder)
- In-process archive job dispatcher (`pending` survives restart)
- Native full-text search (SQLite FTS5 + MySQL FULLTEXT)
- GHCR publish workflow (`mailarchive-api` / `mailarchive-frontend`)
- SMTP Reply-To / timeout; branding; Ko-fi; i18n ES/EN
- Settings (SMTP, templates, language, storage, Microsoft 365, appearance)
- Dashboard metrics; PageShell layout; JWT refresh on 401
- DOMPurify + CSP; SECURITY.md; CONTRIBUTING; issue/PR templates
- Landing site for GitHub Pages (`landing/` + `gh-pages` branch)
- Backup notes, release checklist, living TODO

### Security

- `.cursorrules` removed from version control (local agent rules only)
- Internal audit notes removed from the public tree

## [0.9.0] - 2026-08-05

### Added

- MIT license, OSS scrub of client identity
- Rate limiting on login / register / install
- Public self-register disabled by default
- Alembic migrations covering mail archive schema
- Docker Compose stack (API + frontend; SQLite default, MySQL profile)

[Unreleased]: https://github.com/redmanxp/MailArchive-OSS/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/redmanxp/MailArchive-OSS/releases/tag/v1.0.0
[0.9.0]: https://github.com/redmanxp/MailArchive-OSS/releases/tag/v0.9.0
