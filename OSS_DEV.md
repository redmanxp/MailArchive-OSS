# MailArchive — OSS / lab copy

This tree is for development and Open Source prep.

Keep production deployments on a separate path and never point this `.env`
at a production database or `STORAGE_ROOT`.

**This copy (suggested ports):**
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
