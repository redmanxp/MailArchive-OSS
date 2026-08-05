# MailArchive

Sistema de archivado de correos electrónicos para empresas (self-hosted).

> **Importante:** nunca subas secretos (`.env`, tokens, passwords, certificados, dumps).

## Licencia

[MIT](./LICENSE)

## Stack

| Capa | Tecnologías |
|------|-------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic, MySQL/SQLite, JWT, Pydantic |
| Providers | Microsoft Graph (HTTP), IMAPClient (Gmail futuro) |
| Frontend | React, Vite, TypeScript, Material UI, React Router, Axios |
| Storage | Filesystem local (`mail.eml` + `adjuntos/` + `metadata.json`) |

## Características

- Clean Architecture (API / Use cases / Domain / Infrastructure)
- Multi-tenant (`tenant_id` desde el día 1; install v1 = un tenant)
- RBAC interno (Administrador, Supervisor, Usuario, Solo lectura)
- Proveedores desacoplados vía interfaz `MailProvider`
- Sin PST
- Registro público deshabilitado por defecto (`FEATURE_PUBLIC_REGISTER=false`)
- Rate limiting en login / register / install

## Seguridad / secretos

1. Copiá `.env.example` → `.env` y completá valores locales.
2. El archivo `.env` está en `.gitignore` y **no debe versionarse**.
3. No commitear: credenciales Microsoft, passwords IMAP/SMTP/MySQL, keys PEM, dumps SQL.
4. Si un secreto se filtra: rotarlo de inmediato.

## Arranque (desarrollo)

```bash
# Backend
cd backend
source .venv/bin/activate   # uv venv .venv --python 3.12
export PYTHONPATH=$PWD
uvicorn app.main:app --host 0.0.0.0 --port 18100

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5175
```

Prueba API: `bash scripts/test_phase0.sh http://127.0.0.1:18100`

**Nota DB:** sin Docker/MySQL local se usa `DB_ENGINE=sqlite`. Con Docker: `docker compose up -d` y `DB_ENGINE=mysql` (puerto host 3307).

## Estructura

```
backend/     API FastAPI + Clean Architecture
frontend/    React + Vite
storage/     Datos locales (ignorado por git)
docs/        Documentación
deploy/      Ejemplos systemd / nginx
```
