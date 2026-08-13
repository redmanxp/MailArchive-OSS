# Release readiness — MailArchive OSS v1.0

Maintainer checklist before tagging the first **public** `v1.0.0`.
Status reflects the OSS lab copy (2026-08).

Legend: **BLOCKER** must ship · **SHOULD** strongly expected · **NICE** can slip to v1.1

---

## Verdict

Self-hosted pilots are **ready**. Public **v1.0.0** / **v1.0.1** / **v1.1.0** tagged: GHCR (both packages public), Pages landing, Social preview, docs/CI/Dependabot done.

Post-release hygiene: keep Dependabot PRs reviewed; CI green on `main`; keep public roadmap (landing + README) aligned with `docs/TODO.md`.

---

## 1. Security & trust

| Item | Sev | Notes |
|------|-----|--------|
| MIT `LICENSE` | Done | |
| Secrets scrubbed | Done | Re-scan before every push |
| Public register off by default | Done | `FEATURE_PUBLIC_REGISTER=false` |
| Rate limit login/register/install | Done | In-memory; multi-worker caveat in docs |
| Password policy ≥ 8 (install/change/admin) | Done | Login accepts any length (user-typed) |
| JWT refresh on 401 (frontend) | Done | |
| HTML mail sanitization (DOMPurify / CSP) | Done | |
| OAuth `prompt=select_account` | Done | |
| `SECURITY.md` | Done | |
| Weak secret warning in production | Done | |
| Dependency audit / Dependabot | Done | `.github/dependabot.yml` |

---

## 2. Ops & deployment

| Item | Sev | Notes |
|------|-----|--------|
| Docker Compose API + UI | Done | SQLite default; MySQL profile |
| Alembic migrations = real schema | Done | Incl. FTS `0003` |
| Documented backup/restore | Done | [`docs/BACKUP.md`](./BACKUP.md) |
| Documented upgrade path | Done | Same file, “Upgrade notes” |
| Durable-ish job worker | Done | `pending` survives restart; orphan `running` → failed; dispatcher |
| Health endpoint | Done | `/health` |
| GHCR image + publish workflow | Done | `mailarchive-api` + `mailarchive-frontend` **public**; `publish-ghcr.yml`, `docker-compose.prod.yml` |
| Postgres optional | **NICE** | Roadmap **v1.2** (not started) |

---

## 3. Product completeness

| Item | Sev | Notes |
|------|-----|--------|
| Microsoft 365 archive / restore | Done | |
| IMAP archive / restore | Done | |
| Multi-language UI + email packs | Done | ES/EN (+ drop-in JSON) |
| Editable SMTP templates | Done | |
| Full-text search (FTS5 / MySQL FULLTEXT) | Done | Fallback ILIKE |
| Dashboard metrics + health probes | Done | |
| Branding (name, color, logos) | Done | Defaults + upload |
| S3-compatible object storage | Done | MinIO / AWS S3 / R2 / Wasabi via settings |
| Scheduled archive + historical backfill | Done | Per-account policies |
| Employee departure | Done | Admin wizard |
| Gmail IMAP UI preset | Done | App Password; dedicated OAuth later |
| Delete from archive + exclusions | Done | v1.0.1 tombstones |
| CAS storage + restore to another mailbox + Jobs page | Done | v1.1.0 |
| Retention policies UI | Roadmap v1.2 | Column stub only |
| Gmail OAuth dedicated | Roadmap | IMAP+App Password works |

---

## 4. Open-source hygiene

| Item | Sev | Notes |
|------|-----|--------|
| README + manuals ES/EN | Done | |
| `CONTRIBUTING.md` / `CHANGELOG.md` / CoC | Done | |
| Issue / PR templates | Done | |
| GitHub Actions CI | Done | Ruff, mypy scoped, pytest, tsc, ESLint, compose build |
| Support / donations | Done | Ko-fi `mailarchive` + FUNDING.yml |
| GitHub Social preview (`docs/images/cover.png`) | Done | Uploaded in repo Settings |

---

## 5. Quality & DX

| Item | Sev | Notes |
|------|-----|--------|
| Backend unit/smoke (auth, storage, FTS, …) | Done | Expand as features land |
| Frontend e2e smoke (Playwright) | Done | `e2e/` against running stack |
| OpenAPI `/docs` | Done | FastAPI |
| Pin versions in requirements | Done | |

---

## 6. Docs accuracy

| Item | Sev | Notes |
|------|-----|--------|
| Graph via **httpx** (not SDK) | Done | |
| No PST / open EML layout | Done | |
| Ports / Docker (`8080` UI, `18100` API) | Done | Verify `.env.example` comments |

---

## Suggested release sequence

1. Keep CI green on `main`; triage Dependabot.
2. ~~Social preview~~ Done.
3. ~~Tag v1.0.0 + GHCR~~ Done (`v1.0.0` / `v1.0.1` / `v1.1.0`).
4. Announce with screenshots; optional short demo gif.
5. Keep landing/README roadmap in sync when features ship.

---

## Out of scope for v1.0 (explicit)

- Gmail OAuth provider (IMAP + App Password + UI preset is supported)  
- LDAP / Active Directory SSO  
- Multi-tenant SaaS admin UI  
- Legal hold / retention policy engine (retention UI is v1.2)  
- Mobile-first redesign / dark mode  

Document these on the README **Roadmap** so expectations stay honest.
