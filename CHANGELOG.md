# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Added

- **Employee departure** wizard: `GET/POST /api/v1/admin/users/{id}/departure` + UI `/app/users/:id/departure` (optional bulk archive, disable schedules, transfer/unlink, deactivate; audit `user.departure`)
- Users / Accounts list filters (client-side search + role / provider)
- Standalone `docker-compose.prod.yml` for GHCR pre-built install (no local build)
- Retry failed/cancelled archive jobs (`POST /archive/jobs/{id}/retry`); dashboard archive health (failed jobs, schedule errors, last archive)
- Gmail IMAP UI preset (`imap.gmail.com:993` + App Password hint)
- Docs: manuals cover departure, filters, job retry, Gmail preset, GHCR prod compose; schedule dialog shows last/next run + watermark
- **Scheduled incremental archive** per account (`archive_schedules`, poller, Cuentas → clock icon)
- Admin **transfer** linked mail account to another user (reassigns archived mails)
- Soft-**unlink** account: clears credentials, keeps archive (`status=unlinked`)
- Deactivate user asks: unlink accounts (keep archive) or transfer to another user
- Restore: optional **keep copy in app** (`keep_copy`, default off) for single and bulk restore
- S3-compatible mail storage (`STORAGE_BACKEND=s3`) with MinIO Docker profile; filesystem remains default
- Tenant mode `single` / `multi` (install + Settings): single hides tenant on login/register
- Dependabot weekly updates (pip, npm, GitHub Actions)
- Install wizard: choose SQLite/MySQL and storage folder (restart required when DB engine changes)
- In-process archive job dispatcher: `pending` jobs survive API restart; only `running` jobs are marked failed
- Native full-text search: SQLite FTS5 + MySQL FULLTEXT (migration `0003_mail_fts`), with ILIKE fallback
- GHCR publish workflow (`mailarchive-api` / `mailarchive-frontend`) and `docker-compose.ghcr.yml`
- Backend pytest smoke suite + Ruff in CI
- SMTP Reply-To and configurable timeout (5–120s)
- Tenant appearance: brand name + primary color in Settings → Appearance
- Default MailArchive logos (icon + full) with admin upload/reset via branding API
- Real Ko-fi support link (https://ko-fi.com/mailarchive) with official GitHub button and `.github/FUNDING.yml`
- Frontend ESLint (typescript-eslint + react-hooks) in CI
- Scoped mypy on branding/FTS/jobs helpers in CI
- App-wide i18n (ES/EN) for UI and email templates; language packs under `backend/app/i18n/locales/`
- Settings tabs: SMTP, templates, language, data/storage (editable), Microsoft 365 OAuth, appearance stub
- File-based system overrides (`/data/system_overrides.json`) for DB/storage/Graph without editing `.env`
- Dashboard metrics: users, accounts, mails, storage bytes, attachments, active jobs, DB/storage health
- Users create/edit as a dedicated form (`/app/users/new`, `/app/users/:id`) with `+` on the list
- PageShell layout: fixed header/filters, scrollable body, pagination footer
- Public README with badges, screenshots, roadmap, and support section
- Release checklist and living TODO (`docs/RELEASE_CHECKLIST.md`, `docs/TODO.md`)
- Backup & restore notes (`docs/BACKUP.md`)
- JWT refresh interceptor on frontend 401 responses
- Production warning when default/weak secrets are detected
- DOMPurify for HTML mail bodies + basic CSP meta on the SPA
- GitHub issue / PR templates and Contributor Covenant

### Changed

- Microsoft OAuth uses `prompt=select_account`
- Password minimum length set to 8 for install/change/invite completion schemas
- SMTP settings hint shortened

### Security

- `.cursorrules` removed from version control (local agent rules only)

## [0.9.0] - 2026-08-05

### Added

- MIT license, OSS scrub of client identity
- Rate limiting on login / register / install
- Public self-register disabled by default
- Alembic migrations covering mail archive schema
- Docker Compose stack (API + frontend; SQLite default, MySQL profile)

[Unreleased]: https://github.com/redmanxp/MailArchive-OSS/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/redmanxp/MailArchive-OSS/releases/tag/v0.9.0
