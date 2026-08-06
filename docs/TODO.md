# Pendientes — MailArchive OSS

Lista viva. Release: [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) · Backup: [BACKUP.md](./BACKUP.md)

Leyenda: **P0** bloquea v1.0 · **P1** importante · **P2** luego

---

## Configuración

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| C1 | Datos/storage editable (SQLite vs MySQL + STORAGE_ROOT) | P1 | **Hecho** (overrides en `/data/system_overrides.json`; DB → reinicio API) |
| C2 | Wizard install: DB + carpeta archivos | P1 | Pendiente |
| C3 | Apariencia / branding | P2 | Stub |
| C4 | Microsoft Graph desde UI | P1 | **Hecho** (Settings → Microsoft 365) |
| C5 | SMTP reply-to / timeout | P2 | Pendiente |
| C6 | Warning secretos débiles en prod | P1 | Hecho |

---

## Seguridad

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| S1 | Password ≥8 | P0 | Hecho |
| S2 | JWT refresh FE | P1 | Hecho |
| S3 | OAuth `select_account` | P1 | Hecho |
| S4 | DOMPurify + CSP | P1 | **Hecho** (MailBodyViewer + meta CSP) |
| S5 | Contacto Security Advisories | P1 | Hecho (SECURITY.md) |

---

## Ops / OSS

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| O1–O5 | CONTRIBUTING, CHANGELOG, CI, BACKUP, upgrade | P0 | Hecho |
| O6 | CoC + issue/PR templates | P1 | **Hecho** |
| O7 | GHCR / Docker Hub image | P1 | Pendiente |
| O8 | Ko-fi real | P2 | Placeholder |

---

## Producto

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| P1a | Full-text search nativo (FTS5/FULLTEXT) | P1 | Pendiente (hoy ILIKE amplio en subject/from/body) |
| P2 | Worker durable de jobs | P1 | Pendiente |
| P3 | Dashboard métricas | P1 | Hecho |
| P4–P7 | Gmail, S3, Postgres, retención | P2 | Roadmap |

---

## Calidad

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| Q1 | Tests backend | P1 | Pendiente |
| Q2 | Playwright e2e | P2 | Diferido |
| Q3 | Ruff/mypy/ESLint en CI | P1 | Parcial (tsc + import + docker build) |

---

*Actualizar al cerrar ítems.*
