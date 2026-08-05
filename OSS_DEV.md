# MailArchive — OSS / lab copy

This tree is for development and Open Source prep.

**Production (do not break):** `/mnt/almacen/apps/produccion/m365_archivo`  
Ports prod: API `18100`, UI `5175` (systemd).

**This copy:**
- API: `127.0.0.1:18101`
- UI: `127.0.0.1:5176`
- DB: SQLite under `backend/data/` (see `.env`)
- Storage: `./storage`

## Run

```bash
cd backend
# create venv if missing
uv venv .venv || python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD
# load env from repo root
set -a && source ../.env && set +a
uvicorn app.main:app --host 127.0.0.1 --port 18101

# other terminal
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5176
```

Never point this `.env` at production MySQL or production `STORAGE_ROOT`.
