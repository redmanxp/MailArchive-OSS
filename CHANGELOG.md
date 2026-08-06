# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Install wizard: choose SQLite/MySQL and storage folder (restart required when DB engine changes)
- In-process archive job dispatcher: `pending` jobs survive API restart; only `running` jobs are marked failed
- Native full-text search: SQLite FTS5 + MySQL FULLTEXT (migration `0003_mail_fts`), with ILIKE fallback
- GHCR publish workflow (`mailarchive-api` / `mailarchive-frontend`) and `docker-compose.ghcr.yml`
- Backend pytest smoke suite + Ruff in CI
- SMTP Reply-To and configurable timeout (5–120s)
- Tenant appearance: brand name + primary color in Settings → Appearance
- Real Ko-fi support link (https://ko-fi.com/redmanxp)
- Frontend ESLint (typescript-eslint + react-hooks) in CI
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
