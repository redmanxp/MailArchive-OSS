# Contributing to MailArchive

Thanks for contributing. This project is a self-hosted email archiving platform (MIT).

## Development setup

```bash
# Backend
cd backend
uv venv .venv --python 3.12   # or python3 -m venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD
cp ../.env.example ../.env    # fill secrets
uvicorn app.main:app --host 0.0.0.0 --port 18100

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5175
```

Docker (API + UI):

```bash
cp .env.example .env
docker compose up --build
# UI http://localhost:8080
```

## Guidelines

- Prefer **minimal, focused changes**. Do not refactor unrelated code.
- Keep domain layer free of FastAPI / SQLAlchemy / Graph / IMAP imports.
- Always filter business queries by `tenant_id`.
- UI strings: add keys to `backend/app/i18n/locales/es.json` and `en.json` (and use `t()` / `tf()`).
- Never commit `.env`, tokens, certificates, or real mailbox data.
- Fixed dependency versions in `requirements.txt`.

## Pull requests

1. Describe **why** the change is needed.
2. Note any migration / env / UI impact.
3. Keep PRs reviewable (prefer small scoped PRs).

## Security

Report vulnerabilities privately (see [SECURITY.md](./SECURITY.md)). Do not open public issues with exploit details for unreleased flaws.

## License

By contributing, you agree your contributions are licensed under the MIT License.
