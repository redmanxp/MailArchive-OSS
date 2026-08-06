# Release readiness — MailArchive OSS v1.0

Maintainer checklist before tagging the first **public** `v1.0.0`.
Status reflects the OSS lab copy (2026-08).

Legend: **BLOCKER** must ship · **SHOULD** strongly expected · **NICE** can slip to v1.1

---

## Verdict

Self-hosted pilots are **ready**. Most former blockers (docs, CI, password ≥8, FTS, branding, backup/upgrade, GHCR, Dependabot) are done.

Remaining before a confident public `v1.0.0`: Social preview after the repo is public, and honest “beta vs 1.0” messaging if you want more bake time.

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
| GHCR image + publish workflow | Done | `publish-ghcr.yml`, `docker-compose.prod.yml` (+ overlay `.ghcr.yml`) |
| Postgres optional | **NICE** | Roadmap v1.1 |

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
| Gmail / S3 / retention UI | Roadmap | Do not claim shipped |

---

## 4. Open-source hygiene

| Item | Sev | Notes |
|------|-----|--------|
| README + manuals ES/EN | Done | |
| `CONTRIBUTING.md` / `CHANGELOG.md` / CoC | Done | |
| Issue / PR templates | Done | |
| GitHub Actions CI | Done | Ruff, mypy scoped, pytest, tsc, ESLint, compose build |
| Support / donations | Done | Ko-fi `mailarchive` + FUNDING.yml |
| GitHub Social preview (`docs/images/cover.png`) | **When public** | Settings → General → Social preview |

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

1. Keep CI green on `main`.
2. After making the repo **public**: upload Social preview (`docs/images/cover.png`).
3. Tag **v1.0.0** (or **v0.9.0-beta** if you want more external bake time) + publish GHCR.
4. Announce with screenshots; optional short demo gif.

---

## Out of scope for v1.0 (explicit)

- Gmail OAuth provider  
- S3 / multi-backend storage  
- LDAP / Active Directory SSO  
- Multi-tenant SaaS admin UI  
- Legal hold / retention policy engine  
- Mobile-first redesign / dark mode  

Document these on the README **Roadmap** so expectations stay honest.
