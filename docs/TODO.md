# Pendientes — MailArchive OSS

Lista viva de trabajo. Detalle de release público: [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md).

Leyenda: **P0** bloquea v1.0 · **P1** importante · **P2** luego

---

## Configuración (producto)

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| C1 | **Datos y almacenamiento editable** — elegir motor (SQLite local vs MySQL/Postgres existente), host/credenciales, y `STORAGE_ROOT` desde UI con reinicio guiado | P1 | Parcial: pestaña **Datos** solo lectura |
| C2 | Wizard de instalación: preguntar DB + carpeta de archivos antes/durante bootstrap | P1 | Pendiente |
| C3 | Apariencia / branding (logo, colores) | P2 | Stub en Settings |
| C4 | Microsoft Graph: configurar Client ID/Secret/Tenant desde UI (hoy `.env`) | P1 | Pendiente |
| C5 | SMTP: reply-to, timeout editable | P2 | Pendiente |
| C6 | Validar secretos `change-me-*` al arrancar en `production` | P1 | Hecho (warning en logs) |

---

## Seguridad / auth

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| S1 | Password `min_length≥8` en schemas auth/invite/change | P0 | Hecho |
| S2 | Refresh JWT automático en frontend ante 401 | P1 | Hecho |
| S3 | OAuth Microsoft `prompt=select_account` | P1 | Hecho |
| S4 | Sanitizar HTML del cuerpo (DOMPurify) + CSP básica | P1 | Pendiente |
| S5 | Contacto de seguridad en `SECURITY.md` / GitHub Advisories | P1 | Pendiente |

---

## Ops / release OSS

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| O1 | `CONTRIBUTING.md` | P0 | Hecho |
| O2 | `CHANGELOG.md` | P0 | Hecho |
| O3 | GitHub Actions (lint + smoke + docker build) | P0 | Hecho (workflow básico) |
| O4 | Docs backup/restore (DB + `STORAGE_ROOT`) | P0 | Hecho (`docs/BACKUP.md`) |
| O5 | Docs upgrade path | P0 | Incluido en BACKUP.md |
| O6 | `CODE_OF_CONDUCT` + issue/PR templates | P1 | Pendiente |
| O7 | Imagen publicada (GHCR / Docker Hub) | P1 | Pendiente |
| O8 | Completar enlace Ko-fi real en README | P2 | Placeholder |

---

## Producto / búsqueda / jobs

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| P1a | Full-text search | P1 | Pendiente |
| P2 | Worker durable de jobs | P1 | Pendiente |
| P3 | Dashboard con métricas | P1 | Hecho (`GET /dashboard/metrics`) |
| P4 | Gmail provider | P2 | Roadmap v1.1 |
| P5 | Object storage (S3) | P2 | Roadmap v1.1 |
| P6 | PostgreSQL como motor soportado | P2 | Roadmap |
| P7 | Retención / políticas legales | P2 | Future |

---

## Calidad

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| Q1 | Tests backend mínimos (auth, archive) | P1 | Pendiente |
| Q2 | Playwright e2e smoke | P2 | Diferido |
| Q3 | Ruff/mypy + ESLint en CI | P1 | Parcial (tsc + import + docker build) |

---

## Hecho recientemente

- [x] i18n UI ES/EN + plantillas email
- [x] PageShell + usuarios create/edit
- [x] README EN + screenshots + roadmap
- [x] Hint SMTP corto + pestaña Datos (lectura)
- [x] Métricas dashboard
- [x] Passwords ≥8, OAuth select_account, JWT refresh FE
- [x] CONTRIBUTING, CHANGELOG, BACKUP, CI workflow

---

*Actualizar esta lista al cerrar o abrir ítems.*
