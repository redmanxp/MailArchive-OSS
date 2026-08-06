# MailArchive landing (Vite + React + Tailwind)

Static marketing site deployed to GitHub Pages:

https://redmanxp.github.io/MailArchive-OSS/

## Local

```bash
cd landing
npm install
npm run dev          # http://localhost:5173 (base path still /MailArchive-OSS/)
VITE_BASE=/ npm run dev   # optional root base for local
npm run build
npm run preview
```

## Deploy

Push to `main` under `landing/**` (or run **Deploy landing** workflow manually).

**Blocked while the repo is private:** GitHub Pages on the free plan requires a **public** repository (or a paid plan). When you make the repo public:

1. Settings → Pages → Source: **GitHub Actions**
2. Run workflow **Deploy landing (GitHub Pages)**
3. Site: https://redmanxp.github.io/MailArchive-OSS/

Tracked in `docs/TODO.md` as **O12**.
