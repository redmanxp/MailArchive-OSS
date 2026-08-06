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

Two options (repo must be **public**):

### A — Branch `gh-pages` (simplest)

The static site is already on branch **`gh-pages`**.

1. Open https://github.com/redmanxp/MailArchive-OSS/settings/pages  
2. **Build and deployment** → **Source**: **Deploy from a branch**  
3. Branch: **`gh-pages`** / folder: **`/`** (root) → **Save**  
4. Wait ~1 minute → https://redmanxp.github.io/MailArchive-OSS/

### B — GitHub Actions

1. Settings → Pages → Source: **GitHub Actions**  
2. Actions → **Deploy landing (GitHub Pages)** → **Run workflow**  

Tracked in `docs/TODO.md` as **O12**.
