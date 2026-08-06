# Release readiness — MailArchive OSS v1.0

Maintainer-style checklist before tagging the first **public** `v1.0.0`.
Status reflects the codebase as of the OSS lab copy (2026-08).

Legend: **BLOCKER** must ship · **SHOULD** strongly expected · **NICE** can slip to v1.1

---

## Verdict

Product is **usable for self-hosted pilots**, but not yet a polished GitHub `v1.0` release.
Ship a **v0.9 / beta** tag first if you need a public repo sooner; reserve `v1.0.0` for the blockers below.

---

## 1. Security & trust (BLOCKER / SHOULD)

| Item | Sev | Notes |
|------|-----|--------|
| MIT `LICENSE` present | Done | Keep SPDX in README badges |
| Secrets scrubbed (no real tenants/clients) | Done | Re-scan before every push |
| Public register off by default | Done | `FEATURE_PUBLIC_REGISTER=false` |
| Rate limit login/register/install | Done | In-memory; document multi-worker caveat |
| Password policy ≥ 8 everywhere | **BLOCKER** | Some auth schemas still `min_length=1` |
| JWT refresh on 401 in frontend | **SHOULD** | Tokens in `localStorage`; no auto-refresh |
| HTML mail sanitization (DOMPurify / CSP) | **SHOULD** | Body viewer strips scripts lightly only |
| OAuth `prompt=select_account` | **SHOULD** | Align with product rules |
| `SECURITY.md` + vulnerability contact | **SHOULD** | Contact email / GitHub Security Advisories |
| No default `change-me-*` accepted in production | **SHOULD** | Refuse boot or warn loudly if `APP_ENV=production` |
| Dependency audit / Dependabot | **SHOULD** | No CI Dependabot yet |

---

## 2. Ops & deployment (BLOCKER / SHOULD)

| Item | Sev | Notes |
|------|-----|--------|
| Docker Compose API + UI | Done | SQLite default; MySQL profile |
| Alembic migrations = real schema | Done | Re-verify on clean volume + MySQL |
| Documented backup/restore | **BLOCKER** | DB + `STORAGE_ROOT` procedure |
| Documented upgrade path | **BLOCKER** | `docker compose pull` + migrate notes |
| Durable job worker | **SHOULD** | Jobs in-process threads; restart marks orphan jobs failed |
| Health/readiness for reverse proxy | Done-ish | `/health` exists; document nginx sample |
| Production compose example (MySQL + volumes) | **SHOULD** | Separate from demo SQLite |
| Postgres as optional engine | **NICE** | Common OSS expectation; can be v1.1 |

---

## 3. Product completeness for “v1.0” claim (SHOULD / NICE)

| Item | Sev | Notes |
|------|-----|--------|
| Microsoft 365 archive / restore | Done | |
| IMAP archive / restore | Done | |
| Multi-language UI + email packs | Done | ES/EN; drop JSON to add more |
| Editable SMTP templates | Done | Free text + placeholders |
| Full-text search | **SHOULD** for v1.0 marketing | Today: LIKE / basic filters |
| Dashboard metrics | **NICE** | Counts, storage used, jobs |
| Gmail provider | Roadmap v1.1 | Do not imply shipped |
| Object storage (S3) | Roadmap v1.1 | |
| Legal retention policies UI | Future | |
| Branding / white-label | Future | Appearance tab stub |

---

## 4. Open-source project hygiene (BLOCKER / SHOULD)

| Item | Sev | Notes |
|------|-----|--------|
| README (EN) with screenshots, why, roadmap | Done | Spanish manuals linked |
| `docs/USER_MANUAL.md` + `docs/MANUAL_USUARIO.md` | Done | Keep in sync |
| `docs/RELEASE_CHECKLIST.md` | Done | This file |
| `docs/images/*.png` | Done | Refresh via `scripts/capture-screenshots.mjs` |
| `CONTRIBUTING.md` | **BLOCKER** | How to run, PR style, DCO/CLA if any |
| `CODE_OF_CONDUCT.md` | **SHOULD** | Contributor Covenant |
| Issue / PR templates | **SHOULD** | `.github/ISSUE_TEMPLATE`, `PULL_REQUEST_TEMPLATE` |
| `CHANGELOG.md` (Keep a Changelog) | **BLOCKER** | First entry for v1.0.0 |
| GitHub Actions CI | **BLOCKER** | lint + unit smoke + docker build |
| Tagged release + GHCR or Docker Hub image | **SHOULD** | `ghcr.io/.../mailarchive:1.0.0` |
| Architecture doc (short) | **SHOULD** | Providers, storage layout, multi-tenant |
| Support / donations link | Done | https://ko-fi.com/mailarchive · FUNDING.yml (`ko_fi: mailarchive`) |

---

## 5. Quality & DX (SHOULD / NICE)

| Item | Sev | Notes |
|------|-----|--------|
| Backend tests (auth, archive happy path) | **SHOULD** | Almost none today |
| Frontend e2e smoke (Playwright) | **NICE** | Deferred |
| Ruff / Black / mypy in CI | **SHOULD** | |
| Frontend ESLint in CI | **SHOULD** | |
| OpenAPI published / “Try it” notes | **NICE** | FastAPI `/docs` |
| Pin versions (already in requirements) | Done | Keep discipline |

---

## 6. Docs accuracy (BLOCKER)

| Item | Sev | Notes |
|------|-----|--------|
| README: Graph via **httpx**, not SDK | **BLOCKER** | Audit finding |
| README: “No PST” explained as open EML | Done in new README | |
| `.env.example` matches Docker ports (`8080`) | **SHOULD** | Align `APP_URL` / CORS comments |
| Remove internal host paths from public docs | Done / verify `deploy/` | |

---

## Suggested release sequence

1. **v0.9.0-beta** — public repo, clear “beta”, Docker works, manuals + SECURITY.
2. Close **BLOCKER** rows above.
3. **v1.0.0** — CHANGELOG, CI green, backup/upgrade docs, password policy, honest feature list (FTS if advertised).
4. Announce with screenshots + short demo gif optional.

---

## Out of scope for v1.0 (explicit)

- Gmail OAuth provider  
- S3 / multi-backend storage  
- LDAP / Active Directory SSO  
- Multi-tenant SaaS admin UI  
- Legal hold / retention policy engine  
- Mobile-first redesign / dark mode  

Document these on the README **Roadmap** so expectations stay honest.
