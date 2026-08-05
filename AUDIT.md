# AUDIT.md — MailArchive Open Source Readiness

**Fecha:** 2026-08-05  
**Alcance:** `/mnt/almacen/apps/produccion/m365_archivo` (backend + frontend + Docker + deploy)  
**Regla de esta fase:** solo auditoría; **sin cambios de código**.  
**Veredicto:** producto interno maduro y usable; **aún no listo para release OSS público** sin licencia, scrub de identidad/cliente, rate limiting, migraciones reproducibles, Docker app completo y worker de jobs durable.

Clasificación usada en hallazgos:

| Etiqueta | Significado |
|----------|-------------|
| **CRÍTICO** | Bloquea publicar / riesgo alto de seguridad o datos |
| **IMPORTANTE** | Debe abordarse antes o en v1.0 |
| **MEJORA** | Calidad, DX, escala; se puede planificar en v1.1+ |

---

## 1. Arquitectura actual

### Capas (Clean Architecture aproximada)

| Capa | Ruta |
|------|------|
| API | `backend/app/api/` (`router.py`, `v1/*`, `deps/auth.py`) |
| Application | `backend/app/application/use_cases/{auth,users,install,accounts}/` |
| Domain | `backend/app/domain/{entities,enums,exceptions,interfaces}/` |
| Infrastructure | `backend/app/infrastructure/{persistence,providers,security,storage,email}/` |
| Schemas | `backend/app/schemas/` |
| Frontend | `frontend/src/{pages,components,layouts,auth,api}/` |

**Patrones:** Repository + interfaz `MailProvider`; DI manual vía FastAPI `Depends` (sin contenedor).  
**Domain limpio:** no importa FastAPI/SQLAlchemy/Graph/IMAP (**MEJORA** — mantener).

### Hallazgos arquitectura

| Sev | Hallazgo |
|-----|----------|
| **IMPORTANTE** | Application importa Infrastructure concreto (repos SQLAlchemy, Fernet, SessionLocal). No es Clean “pura”; documentar como *pragmatic clean* o desacoplar en v1.1. |
| **MEJORA** | Carpetas vacías: `api/middleware/`, `application/dto/`, `application/services/`, `use_cases/admin/`, `domain/value_objects/`. |
| **MEJORA** | DI ad-hoc en cada endpoint → difícil de testear en OSS. |
| **MEJORA** | `StartBulkArchiveUseCase` en `bulk_archive.py` no cableado; el start real vive en `api/v1/jobs.py` (duplicación parcial). |

---

## 2. Flujo de autenticación

```
Install bootstrap → admin + tenant
     ↓
Login (email + password + tenant_slug) → JWT access + refresh (rotatorio)
     ↓
must_change_password → /set-password o /change-password
     ↓
Alta pública / Admin invite → JWT link 48h (pwd_fp) → set password
```

| Pieza | Estado | Ubicación |
|-------|--------|-----------|
| JWT HS256 + refresh `jti` hash | OK | `jwt_service.py`, `auth_use_cases.py` |
| Argon2 | OK | `argon2_hasher.py` |
| Gate must_change_password | OK | `api/deps/auth.py` |
| Invite / reset 48h | OK | `password_link.py`, `user_management.py` |
| RBAC roles | OK | admin / supervisor / user / readonly |

| Sev | Hallazgo |
|-----|----------|
| **CRÍTICO** | `POST /auth/register` abierto sin rate-limit/captcha → abuso si se publica. |
| **IMPORTANTE** | Política password débil en change/invite (`min_length=1` en parte de schemas). |
| **IMPORTANTE** | Frontend: access+refresh en `localStorage`; **sin** refresh automático ante 401. |
| **IMPORTANTE** | Defaults UI install/login: tenant/email/password de cliente MAPS (`InstallPage`, `LoginPage`). |
| **MEJORA** | Install puede devolver temporary_password en claro (OK en install controlado; documentar). |
| **MEJORA** | Defaults `SECRET_KEY` / `change-me-*` y `APP_DEBUG=True` en `config.py`. |

---

## 3. Flujo Microsoft Graph

**Estado: implementado** (REST + `httpx`, **no** SDK pese a lo que dice el README).

```
UI → /accounts/microsoft/oauth/start → Entra ID
   → callback + state HMAC → tokens Fernet en DB
   → MicrosoftGraphProvider (folders, MIME, delete, restore, refresh)
```

| Sev | Hallazgo |
|-----|----------|
| **IMPORTANTE** | OAuth usa `prompt=login`; `.cursorrules` pide `select_account`. |
| **MEJORA** | README dice “Graph SDK”; no está en `requirements.txt`. |
| **MEJORA** | Algunos métodos del provider tienen código confuso/muerto (`archive_message` descarga y descarta). |

---

## 4. Flujo Gmail

**No implementado.** Solo enum `MailProviderType.GMAIL` + `NotImplementedError` en factory + label UI.

| Sev | Hallazgo |
|-----|----------|
| **IMPORTANTE** (roadmap OSS) | Gmail OAuth es expectativa natural de un producto multi-proveedor. Planificar v1.1/v2.0. |
| **MEJORA** | No exponer Gmail en UI de producción hasta tener provider, o marcar “Coming soon”. |

---

## 5. Organización del backend

```
backend/app/
  api/v1/          auth, install, admin, accounts, jobs, archive
  application/     use_cases (auth, users, install, accounts)
  domain/          entities, enums, exceptions, interfaces (MailProvider, repos)
  infrastructure/  persistence, providers (Graph, IMAP), security, storage, email
  schemas/         Pydantic
  config.py, main.py
backend/alembic/   migración 0001 incompleta vs modelos actuales
```

Proveedores: `microsoft_graph.py`, `imap_provider.py`, `factory.py`.  
Storage EML: `{storage_root}/{tenant}/{account}/{yyyy}/{mm}/{mail_id}/`.

---

## 6. Organización del frontend

```
frontend/src/
  pages/       ~15 pantallas (login, install, dashboard, accounts, archive, bulk, mails, admin…)
  components/  ConfirmDialog, MailBodyViewer, BulkPreparingModal
  layouts/     AppLayout (drawer permanente)
  auth/        AuthContext
  api/         client.ts (~622 líneas, Axios)
  theme.ts     light fijo
```

Stack: React 18, Vite 6, MUI 6, React Router 6, TypeScript strict.

| Sev | Hallazgo |
|-----|----------|
| **IMPORTANTE** | Drawer no responsive (móvil). |
| **IMPORTANTE** | 100 % strings en español hardcodeado (sin i18n). |
| **IMPORTANTE** | Dashboard = launcher sin métricas. |
| **MEJORA** | Sin dark mode; empty states mínimos; `formatBytes` duplicado. |
| **MEJORA** | Sin `.env.example` en `frontend/` (`VITE_API_URL`). |

---

## 7. Modelo de base de datos

| Tabla | ID | Notas |
|-------|-----|-------|
| `tenants`, `users`, `refresh_tokens`, `audit_logs` | BIGINT | Multi-tenant |
| `mail_accounts` | BIGINT | Credenciales cifradas Fernet |
| `archived_mails` | **UUID** PK | Storage path + API pública |
| `attachments` | BIGINT | Metadata |
| `archive_jobs` | BIGINT | Progreso en columnas |
| `tenant_settings`, `install_state` | — | SMTP / features / install |

**Engines hoy:** `DB_ENGINE=sqlite|mysql` (`config.py`).  
**Postgres:** no cableado aún (ver § recomendaciones multi-DB).

| Sev | Hallazgo |
|-----|----------|
| **CRÍTICO** | Alembic `0001_phase0.py` **no** crea accounts/mails/jobs/attachments. Deploy real usa `create_all` → installs “solo migrate” rotos. |
| **IMPORTANTE** | FullText MySQL “preparado” en reglas, **no** implementado; búsqueda = `ILIKE %q%`. |
| **MEJORA** | `storage_quota_bytes` en settings sin enforcement claro en jobs. |
| **MEJORA** (producto) | Documentar y soportar **SQLite (dev/small) · MySQL · PostgreSQL** vía SQLAlchemy URL. |

---

## 8. Docker

| Pieza | Estado |
|-------|--------|
| `docker-compose.yml` | Solo **MySQL 8.4** (host 3307) |
| Dockerfile API / FE | **No** |
| `docker compose up` one-shot app | **No** |

| Sev | Hallazgo |
|-----|----------|
| **CRÍTICO** (OSS DX) | Sin stack app reproducible con un comando. |
| **IMPORTANTE** | Deploy systemd/nginx con paths `/mnt/almacen/...` y usuario `pablo` — interno MAPS, no genérico. |
| **IMPORTANTE** | `deploy/sudoers/` en repo: útil localmente; no publicar sin ejemplos neutros. |

---

## 9. Seguridad

| Control | Estado |
|---------|--------|
| `.gitignore` / `SECURITY.md` / no commit `.env` | OK |
| Fernet (OAuth + IMAP) | OK |
| RBAC + audit logs | OK |
| Rate limiting | **Anunciado en `.env.example`, no implementado** |
| CSRF | N/A Bearer; sin cookies session |
| Password Microsoft | No se guarda | 

| Sev | Hallazgo |
|-----|----------|
| **CRÍTICO** | Rate limit ausente + register abierto. |
| **CRÍTICO** | Defaults install FE con password de ejemplo de cliente. |
| **IMPORTANTE** | Tokens en `localStorage` + XSS residual en HTML viewer (`MailBodyViewer`). |
| **IMPORTANTE** | `.env.example` con hosts/tenant de organización — sanitizar. |
| **IMPORTANTE** | `APP_DEBUG` default True → SQL echo. |
| **MEJORA** | Valorar PyJWT vs `python-jose`; CSP en frontend. |

---

## 10. Rendimiento

| Sev | Hallazgo |
|-----|----------|
| **IMPORTANTE** | Jobs = **threads in-process**; 1 worker uvicorn; restart → pending/running → failed. |
| **IMPORTANTE** | Búsqueda ILIKE full scan; no escala a cientos de miles de mails. |
| **IMPORTANTE** | IMAP `list_messages` limita/trunca; Graph walks de carpetas costosos. |
| **MEJORA** | Sin object storage; sin pool MySQL tuneado; SQLite + threads. |

---

## 11. Código duplicado

- Flujo start bulk: use case no usado vs lógica en `jobs.py`.
- `formatBytes` ×4 en frontend.
- Criterios de listado Graph vs IMAP (capacidades asimétricas).

---

## 12. Componentes innecesarios / archivos muertos

| Tipo | Detalle |
|------|---------|
| Carpetas vacías | middleware, dto, services, admin use_cases, value_objects |
| Use case huérfano | `StartBulkArchiveUseCase` |
| Enum sin provider | Gmail |
| Deploy site-specific | systemd/nginx/sudoers con paths host |
| LICENSE | **Ausente** (README: uso interno) |

No hay páginas FE huérfanas; `package.json` deps justificadas.

---

## 13. Dependencias eliminables / inconsistentes

| Item | Acción |
|------|--------|
| Microsoft Graph SDK | No está; **actualizar README** (no instalar si REST basta) |
| `RATE_LIMIT_ENABLED` en example | Implementar o quitar |
| `python-multipart` | Dejar (FastAPI) o documentar |
| Frontend | Sin ESLint/Vitest en scripts — agregar en FASE 4 |

---

## 14. Bugs potenciales

| Sev | Bug |
|-----|-----|
| **IMPORTANTE** | Cancel job solo in-memory → no sobrevive restart / multi-worker. |
| **IMPORTANTE** | Alembic incompleto. |
| **IMPORTANTE** | OAuth prompt ≠ select_account. |
| **IMPORTANTE** | FE no renueva JWT → errores silenciosos tras ~15 min. |
| **MEJORA** | Passwords de 1 carácter vía invite. |
| **MEJORA** | RBAC UI: `readonly` aún ve Archivar/Masivo (backend debe bloquear; UX confusa). |

---

## 15. Escalabilidad

| Tema | Hoy | Riesgo |
|------|-----|--------|
| Jobs | Thread local | No horizontal |
| DB search | ILIKE | CPU/IO |
| Storage | FS local | Un solo nodo |
| API workers | 1 (jobs) | Throughput limitado |
| Multi-tenant SaaS UI | Un tenant install | OK v1; SaaS UI = v2 |

---

## 16. Deuda técnica (mapa vs fases propuestas)

| Deuda | Fase sugerida |
|-------|----------------|
| i18n ES/EN | FASE 2 |
| LICENSE, README OSS, templates GH | FASE 3 |
| Lint, tests, CI | FASE 4 |
| UX dashboard, dark, empty, responsive | FASE 5–6 |
| Jobs durable (cola) | FASE 7 |
| FullText / filtros avanzados | FASE 8 |
| Rate limit, scrub secrets, DOMPurify | FASE 9 |
| Índices, batch, memoria | FASE 10 |
| Gmail, filtros, export, OpenAPI polish | FASE 11 |
| `docker compose up` app+db | FASE 12 |
| Refactors puntuales | FASE 13 |
| Docs arquitectura/API | FASE 14 |
| ROADMAP + RELEASE_CHECKLIST | FASE 15 |
| Multi-DB (SQLite/MySQL/Postgres) | FASE 12 + 10 (config + docs) |

---

## 17. Multi-base de datos (requisito de producto)

**Hoy:** SQLite y MySQL vía `DB_ENGINE` / connection string.  
**Objetivo OSS:** el usuario elige:

| Motor | Uso típico |
|-------|------------|
| **SQLite** | Demo, single-node, pocos usuarios |
| **MySQL / MariaDB** | Producción actual MAPS |
| **PostgreSQL** | Estándar OSS / cloud |

**Recomendación (proponer antes de implementar):**

1. Unificar en `DATABASE_URL` (SQLAlchemy) + ejemplos en `.env.example`.
2. Alembic migrations **únicas** compatibles con los tres (tipos UUID/JSON con cuidado).
3. FullText: MySQL `FULLTEXT` / Postgres `tsvector` / SQLite FTS5 — capa de búsqueda abstracta.
4. Documentar límites (SQLite + jobs concurrentes).

Severidad de no tenerlo documentado/cableado para Postgres: **IMPORTANTE** (expectativa OSS).

---

## 18. Ángulo legal / retención (para README “venta”)

> **Disclaimer:** no es asesoramiento legal. Citar como *motivación típica* y remisión a asesoría local.

Muchas industrias deben **conservar correspondencia electrónica** años:

| Ámbito | Referencia típica | Orden de magnitud |
|--------|-------------------|-------------------|
| Salud / HIPAA (EE.UU.) | Retention policies de ePHI / business records | a menudo **6+ años** según tipo de registro |
| UE / GDPR | Minimización + obligaciones sectoriales; ePrivacy | retención **justificada** + plazos locales |
| Servicios financieros | SEC / MiFID II / normativas locales | frecuentemente **5–7 años** (comunicaciones) |
| Legal / abogados | Deontología y plazos de expediente | suele **5–10 años** según jurisdicción |
| Argentina / LatAm | Código Civil/Comercial, AFIP, salud, laboral | plazos **variables** (años); correo como prueba documental |
| ISO / compliance corporativo | Políticas internas + eDiscovery | archivo buscable e íntegro (hash) |

**Propuesta de valor MailArchive (copy README):**

- Conservar EML + adjuntos + hash (integridad) sin depender del buzón vivo de Microsoft/Google.
- Liberar cuota del proveedor **sin perder** el historial exigido por compliance.
- Multi-cuenta, multi-usuario, auditoría y export para eDiscovery.
- Self-hosted: los datos no salen a un SaaS de terceros.

---

## 19. Estado vs fases del plan OSS (gap analysis)

| Fase | ¿Ya existe algo? | Gap principal |
|------|------------------|---------------|
| 1 Auditoría | Este documento | — |
| 2 i18n | No | 100 % hardcode ES |
| 3 Open Source pack | README/SECURITY parcial | LICENSE, CoC, templates, donaciones |
| 4 Calidad | TypeScript strict | Black/Ruff/mypy, tests, Actions |
| 5 UX | UI funcional | Dark, móvil, empty, animaciones |
| 6 Dashboard métricas | No | Endpoints + cards |
| 7 Cola jobs | Jobs DB + thread | Pausar/reanudar, worker externo |
| 8 Búsqueda | LIKE básico | FullText, tags, filtros ricos |
| 9 Seguridad | Base sólida | Rate limit, scrub, CSP, refresh FE |
| 10 Escalabilidad | Limitada | Índices, batch, memoria |
| 11 Features | Archivo/simulación/restore | Gmail, export, filtros, OpenAPI |
| 12 Docker | Solo MySQL | App + FE + choose DB |
| 13 Código | Deuda media | Dead code, unificar bulk start |
| 14 Docs | Manual usuario corto | Arquitectura, API, providers |
| 15 v1.0 | — | ROADMAP + RELEASE_CHECKLIST |

---

## 20. Recomendaciones priorizadas

### CRÍTICO (antes de hacer el repo público)

1. Añadir **LICENSE** (MIT/Apache-2.0 a elegir) y scrub de identidad MAPS/Newlici en FE/defaults/`.env.example`.
2. Implementar **rate limiting** (login/register/install) o desactivar register público por default.
3. Migraciones **Alembic = modelo real**; dejar de depender solo de `create_all` en installs limpios.
4. **Docker Compose** con API + frontend (+ opción SQLite embebida o MySQL/Postgres).
5. Quitar o mover a `deploy/examples/` paths absolutos y sudoers del host interno.

### IMPORTANTE (v1.0)

6. Refresh JWT automático en frontend + manejo 401.
7. Jobs: cola durable (RQ/ARQ/Celery o al menos proceso worker) + estados pausado/reanudar.
8. i18n ES/EN; responsive drawer; dashboard métricas básicas.
9. Sanitizar HTML (DOMPurify); política de passwords ≥8.
10. `DATABASE_URL` + PostgreSQL; documentar conectores.
11. Alinear OAuth `prompt=select_account`; actualizar README (httpx, no SDK).
12. FullText o motor de búsqueda mínimo viable.

### MEJORA (v1.1+)

13. Gmail provider; object storage opcional; CSP; PyJWT.  
14. Export CSV/XLSX/ZIP; tags; OpenAPI pulido.  
15. Tests e2e; dark mode; empty states ricos.  
16. Limpiar carpetas vacías y use case huérfano.

---

## 21. Decisión de arquitectura a validar contigo (antes de FASE 7 / 12)

| Tema | Opción A (simple) | Opción B (escala) |
|------|-------------------|-------------------|
| Jobs | Worker aparte + misma DB (polling) | Redis + ARQ/RQ |
| Búsqueda | FULLTEXT nativo por motor | OpenSearch/Meilisearch opcional |
| Multi-DB | Solo SQLAlchemy + Alembic | + capa search por dialecto |

**Propuesta por defecto para OSS v1.0:** Opción A (simplicidad, un solo `docker compose`).

---

## 22. Próximo paso

**FASE 1 completa** con este archivo.

Según tu plan: *detenerse → verificar → commit descriptivo → continuar*.

**Siguiente:** FASE 2 (i18n ES/EN) **solo tras tu OK explícito**.  
En paralelo se puede ir abriendo LICENSE + scrub CRÍTICO (parte FASE 3/9) si preferís desbloquear publicación antes que i18n.

---

*Generado en FASE 1 — auditoría. No se modificó código de aplicación.*
