# Pendientes — MailArchive OSS

Lista viva. Release: [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) · Backup: [BACKUP.md](./BACKUP.md)

Leyenda: **P0** bloquea v1.0 · **P1** importante · **P2** luego

**Producto:** archivo corporativo de correo self-hosted (“mini-archivador”), no sync de buzón.
Lenguaje: **scheduled incremental archive** — nunca “email sync” (evita expectativa de espejo/bidireccional/tiempo real).

---

## Configuración

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| C1 | Datos/storage editable (SQLite vs MySQL + STORAGE_ROOT) | P1 | **Hecho** (overrides en `/data/system_overrides.json`; DB → reinicio API) |
| C2 | Wizard install: DB + carpeta archivos | P1 | **Hecho** (InstallPage + overrides; 409 si cambia motor) |
| C3 | Apariencia / branding | P2 | **Hecho** (logos default + upload; nombre + color) |
| C4 | Microsoft Graph desde UI | P1 | **Hecho** (Settings → Microsoft 365) |
| C5 | SMTP reply-to / timeout | P2 | **Hecho** |
| C6 | Warning secretos débiles en prod | P1 | Hecho |
| C7 | Modo tenant single/multi (install + Settings; login sin slug en single) | P1 | **Hecho** |

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
| O7 | GHCR / Docker Hub image | P1 | **Hecho** (`mailarchive-api` + `mailarchive-frontend` públicos en GHCR; `docker-compose.prod.yml`; Docker Hub diferido) |
| O8 | Ko-fi real | P2 | **Hecho** (https://ko-fi.com/mailarchive · botón F6V224JUWU · `.github/FUNDING.yml`) |
| O9 | GitHub Social preview (cover) | P2 | **Hecho** (`docs/images/cover.png` + Social preview en Settings) |
| O10 | Dependabot | P2 | **Hecho** (`.github/dependabot.yml`) |
| O11 | Screenshots README: redactar emails **y hostnames** (SMTP/IMAP) a `*.example.com` | P1 | **Hecho** (script `capture-screenshots.mjs`) |
| O12 | Landing Pages (`landing/` + workflow `pages.yml`) | P2 | **Hecho** — https://redmanxp.github.io/MailArchive-OSS/ (`gh-pages`) |

---

## Producto

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| P1a | Full-text search nativo (FTS5/FULLTEXT) | P1 | **Hecho** |
| P2 | Worker durable de jobs | P1 | **Hecho** |
| P3 | Dashboard métricas | P1 | Hecho |
| P4 | Gmail OAuth dedicado | P3 | **Diferido** — Gmail vía IMAP + App Password |
| P4b | Preset UI IMAP Gmail (host/puerto + hint App Password) | P2 | **Hecho** |
| P5 | Object storage S3 | P1 | **Hecho** |
| P5b | Restore **keep_copy** | P1 | **Hecho** |
| P5b2 | Restaurar a **otra cuenta** (usuario=suyas; admin/supervisor=cualquier activa) | P1 | **Hecho** (`target_account_id`; destino ≠ origen → keep_copy) |
| P5c | Export EML/ZIP | P1 | **Hecho** |
| P5d | Dedup de **storage** (CAS + Message-ID + refcount; FS + S3) | P1 | **Hecho** (`content_blobs`, skip por RFC Message-ID) |
| P6 | Postgres opcional | P2 | v1.2 |
| P7 | Políticas de retención UI | P2 | v1.2 — ver notas de diseño abajo |
| P7b | Legal hold / inmutabilidad | P2 | v2.0 (prioridad compliance **antes** que P5d) — ver notas abajo |
| P8 | **Scheduled incremental archive** (políticas por cuenta; NO “sync”) | P1 | **Hecho** (tabla `archive_schedules` + dispatcher 30s + UI reloj en Cuentas) |
| P8b | Estado de archivo por cuenta + retry jobs fallidos | P1 | **Hecho** (retry `POST …/jobs/{id}/retry`; dashboard: fallidos / schedules con error / último archivo) |
| P8c | Worker cola externa (Redis/Celery) | P2 | v1.2 |
| P9 | **Transferir cuenta vinculada** a otro usuario (admin) | P1 | **Hecho** (`POST /accounts/{id}/transfer`) |
| P9b | Desvincular cuenta: **conservar archivados**; revocar tokens | P1 | **Hecho** (soft-unlink `status=unlinked`; FK intacta) |
| P9c | Desactivar usuario: diálogo — transferir cuentas · o desvincular (conservar archivo) | P1 | **Hecho** (default unlink; sin borrar EML) |
| P9d | Usuarios: pestaña Desactivados + reactivar + hard-delete (reasignar cuentas; sin purgar EML) | P1 | **Hecho** |
| P9e | Cuentas: pestaña Desvinculadas + reconectar + hard-delete vínculo (bloquea si hay archivados) | P1 | **Hecho** |
| P9f | Purgar archivo de cuenta desvinculada (confirmación ELIMINAR; borra EML+DB+vínculo) | P1 | **Hecho** |
| P10 | **Employee departure archive** — “Archivar buzón de empleado” | P1 | **Hecho** (`GET/POST /admin/users/{id}/departure`; UI `/app/users/:id/departure`) |

---

### Modelo mental (cuentas vs archivo)

| Acción | Cuentas vinculadas | Correos archivados | Acceso app |
|--------|--------------------|--------------------|------------|
| Usuario desvincula cuenta | Se borra el vínculo / tokens | **Se conservan** (default) | Sin cambio |
| Admin transfiere cuenta | `user_id` → otro usuario | Ideal: reasignar `user_id` del mail o dejar visible a Admin/Supervisor | — |
| Admin desactiva usuario | Preguntar: transferir / conservar sin dueño (solo Admin/Supervisor) / eliminar vínculo | Conservar salvo opción explícita “eliminar archivo” | Login bloqueado |
| Admin borra usuario | Igual que desactivar + confirmación fuerte | **Nunca** borrar archivo en silencio | Usuario eliminado |
| Employee departure | Tras archivar: transferir a admin o desvincular | Quedan consultables | Usuario inactivo |

Reglas: **nunca borrar EML por defecto**; borrado de archivo = confirmación explícita (doble) + audit log.

---

### Notas de diseño (local — roadmap futuro; no implementar sin pedido)

**Dedup actual (ya shipped):** por `provider_message_id` (+ aliases IMAP) + SHA-256 del EML + tombstones `archived_mail_exclusions`. Evita re-descargar/re-archivar. Es el dedup correcto para el producto día a día.

**P5d — Dedup de storage (hecho):** blobs CAS `{tenant}/cas/eml|att/{sha256}` + sidecar `metadata.json` por mail + `content_blobs.refcount`. Skip de descarga si el RFC Message-ID ya existe en el tenant (identidad from/subject/sent_at ±120s). Legal hold/retention siguen después; no confundir con el dedup id+SHA+tombstones ya shipped.

**P7b — Legal hold:** tabla tipo `legal_holds` (scope: cuenta, remitente, rango fechas, o mails concretos) que **bloquea cualquier borrado** (manual, retention, purge cuenta/usuario). Mismo patrón que exclusiones pero invertido. Roles Admin/Supervisor aplican/levantan; audit trail obligatorio. Complejidad real = **un check central** en todas las rutas de delete (evitar que un endpoint nuevo se olvide).

**P7 — Retention policies:** policy por scope (tenant/cuenta/carpeta) + regla de edad (“borrar después de X años”) + job programado reusando infraestructura de schedules. Siempre respetar holds activos.

**Orden sugerido para roadmap público (cuando se actualice README/landing):** CAS ya shipped; siguiente compliance = retention + legal hold.

---

## Documentación

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| D1 | Manual completo ES + EN | P1 | **Hecho** |
| D2 | README archivo corporativo + roadmap scheduled / offboarding / transfer | P1 | **Hecho** |

---

## Calidad

| # | Tarea | Pri | Estado |
|---|--------|-----|--------|
| Q1 | Tests backend | P1 | **Hecho** |
| Q2 | Playwright e2e | P2 | **Hecho** |
| Q3 | Ruff/mypy/ESLint en CI | P1 | **Hecho** (Ruff + ESLint + tsc; mypy scoped incl. departure) |

---

*Actualizar al cerrar ítems.*
