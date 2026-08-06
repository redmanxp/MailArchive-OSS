import { useEffect, useState } from "react";

const REPO = "https://github.com/redmanxp/MailArchive-OSS";
const KOFI = "https://ko-fi.com/F6V224JUWU";
const KOFI_PAGE = "https://ko-fi.com/mailarchive";
const MANUAL_EN = `${REPO}/blob/main/docs/USER_MANUAL.md`;
const MANUAL_ES = `${REPO}/blob/main/docs/MANUAL_USUARIO.md`;

const NAV = [
  { id: "home", label: "Home" },
  { id: "features", label: "Features" },
  { id: "installation", label: "Installation" },
  { id: "docker", label: "Docker" },
  { id: "microsoft365", label: "Microsoft 365" },
  { id: "imap", label: "IMAP" },
  { id: "roadmap", label: "Roadmap" },
  { id: "faq", label: "FAQ" },
] as const;

function asset(path: string) {
  const base = import.meta.env.BASE_URL || "/";
  return `${base}${path.replace(/^\//, "")}`;
}

function KofiButton({ className = "" }: { className?: string }) {
  return (
    <a
      href={KOFI}
      target="_blank"
      rel="noreferrer"
      className={`inline-flex items-center gap-2 rounded-full bg-[#FF5E5B] px-4 py-2 text-sm font-semibold text-white shadow-lift transition hover:brightness-110 ${className}`}
    >
      <span aria-hidden>☕</span>
      Support on Ko-fi
    </a>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-2xl border border-white/10 bg-ink p-4 text-sm leading-relaxed text-mist shadow-lift">
      <code>{children}</code>
    </pre>
  );
}

export default function App() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen">
      <header
        className={`fixed inset-x-0 top-0 z-50 transition ${
          scrolled ? "border-b border-ink/10 bg-foam/90 backdrop-blur-md" : "bg-transparent"
        }`}
      >
        <div className="section-pad mx-auto flex max-w-6xl items-center justify-between py-3">
          <a href="#home" className="flex items-center gap-3">
            <img src={asset("images/logo-icon.png")} alt="" className="h-9 w-9 rounded-lg" />
            <span className="font-display text-lg font-bold tracking-tight text-ink sm:text-xl">
              MailArchive
            </span>
          </a>
          <nav className="hidden items-center gap-1 lg:flex">
            {NAV.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="rounded-full px-3 py-1.5 text-sm font-medium text-ink/70 transition hover:bg-mist hover:text-ink"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="hidden items-center gap-2 lg:flex">
            <KofiButton />
            <a
              href={REPO}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:border-teal"
            >
              GitHub
            </a>
          </div>
          <button
            type="button"
            className="rounded-lg border border-ink/15 px-3 py-2 text-sm font-semibold lg:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label="Menu"
          >
            Menu
          </button>
        </div>
        {open && (
          <div className="border-t border-ink/10 bg-foam px-5 py-4 lg:hidden">
            <div className="flex flex-col gap-2">
              {NAV.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className="rounded-lg px-3 py-2 text-sm font-medium hover:bg-mist"
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </a>
              ))}
              <KofiButton className="mt-2 justify-center" />
            </div>
          </div>
        )}
      </header>

      <main>
        {/* HOME */}
        <section id="home" className="relative min-h-[100svh] overflow-hidden">
          <div className="mesh absolute inset-0" />
          <div className="section-pad relative mx-auto flex min-h-[100svh] max-w-6xl flex-col justify-end gap-10 pb-16 pt-28 lg:justify-center lg:pb-24">
            <div className="max-w-2xl animate-fadeUp">
              <p className="mb-4 font-display text-sm font-semibold uppercase tracking-[0.2em] text-teal-bright">
                Open source · Self-hosted
              </p>
              <h1 className="font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-6xl">
                MailArchive
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-mist/90 sm:text-xl">
                Centralize organizational email in one searchable archive you host and control —
                Microsoft 365 and IMAP, without PST lock-in.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <a
                  href="#installation"
                  className="rounded-full bg-teal-bright px-5 py-3 text-sm font-bold text-ink transition hover:bg-white"
                >
                  Get started
                </a>
                <a
                  href="#features"
                  className="rounded-full border border-white/25 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
                >
                  Explore features
                </a>
                <KofiButton />
              </div>
            </div>
            <div className="relative ml-auto w-full max-w-3xl animate-fadeUp lg:absolute lg:bottom-16 lg:right-8 lg:w-[54%]">
              <div className="animate-drift">
              <img
                src={asset("images/cover.png")}
                alt="MailArchive product cover"
                className="w-full rounded-2xl border border-white/15 shadow-lift"
              />
              </div>
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section id="features" className="section-pad mx-auto max-w-6xl py-24">
          <div className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Features</h2>
            <p className="mt-3 text-lg text-ink/70">
              A corporate email archive — not a real-time mailbox sync. Keep searchable copies under
              your governance.
            </p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-2">
            {[
              {
                title: "Multi-account archiving",
                body: "Microsoft 365 / Exchange Online (Graph OAuth) and generic IMAP. Multiple mailboxes in one place.",
              },
              {
                title: "Fast full-text search",
                body: "Browse history without the live provider. Download EML/ZIP or restore messages back to the mailbox.",
              },
              {
                title: "RBAC & audit",
                body: "Admin, Supervisor, User, and Read-only roles. Sensitive actions leave an audit trail.",
              },
              {
                title: "Open storage",
                body: "Standard EML + attachments + metadata (SHA-256). Filesystem or S3-compatible object storage.",
              },
              {
                title: "Scheduled incremental archive",
                body: "Per-account policies that pull new mail into the archive — without implying bidirectional sync.",
              },
              {
                title: "Offboarding ready",
                body: "Transfer accounts, soft-unlink while keeping archive, deactivate users, or purge with explicit confirmation.",
              },
            ].map((f) => (
              <article
                key={f.title}
                className="rounded-3xl border border-ink/10 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lift"
              >
                <h3 className="font-display text-xl font-bold">{f.title}</h3>
                <p className="mt-2 text-ink/70">{f.body}</p>
              </article>
            ))}
          </div>
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["login.png", "Login"],
              ["dashboard.png", "Dashboard"],
              ["archive.png", "Archived search"],
              ["accounts.png", "Accounts"],
            ].map(([src, alt]) => (
              <figure key={src} className="overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-sm">
                <img src={asset(`images/${src}`)} alt={alt} className="w-full" loading="lazy" />
                <figcaption className="px-4 py-2 text-sm text-ink/60">{alt}</figcaption>
              </figure>
            ))}
          </div>
        </section>

        {/* INSTALLATION */}
        <section id="installation" className="border-y border-ink/10 bg-mist/60">
          <div className="section-pad mx-auto max-w-6xl py-24">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Installation</h2>
            <p className="mt-3 max-w-2xl text-lg text-ink/70">
              Copy environment placeholders, build with Docker Compose, open the UI, and complete the
              install wizard.
            </p>
            <div className="mt-10 grid gap-8 lg:grid-cols-2">
              <div className="space-y-4">
                <CodeBlock>{`git clone ${REPO}.git
cd MailArchive-OSS
cp .env.example .env
# set SECRET_KEY, JWT, Fernet, APP_URL, …
docker compose up --build
# UI  http://localhost:8080
# API http://localhost:18100/health`}</CodeBlock>
                <p className="text-sm text-ink/60">
                  Docs:{" "}
                  <a className="font-semibold text-teal underline" href={MANUAL_EN}>
                    User manual (EN)
                  </a>{" "}
                  ·{" "}
                  <a className="font-semibold text-teal underline" href={MANUAL_ES}>
                    Manual (ES)
                  </a>
                </p>
              </div>
              <ul className="space-y-3 text-ink/80">
                {[
                  "Never commit .env or real credentials",
                  "SQLite by default for labs; MySQL via compose profile",
                  "Public self-register is off by default",
                  "Alembic migrations run on API startup",
                ].map((t) => (
                  <li key={t} className="flex gap-3 rounded-2xl bg-white px-4 py-3 border border-ink/10">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-teal" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* DOCKER */}
        <section id="docker" className="section-pad mx-auto max-w-6xl py-24">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Docker</h2>
          <p className="mt-3 max-w-2xl text-lg text-ink/70">
            Local compose stack or pull pre-built images from GitHub Container Registry.
          </p>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="font-display text-xl font-bold">Compose (build)</h3>
              <div className="mt-4">
                <CodeBlock>{`docker compose up --build
# Optional MySQL
docker compose --profile mysql up --build
# Optional MinIO (S3 lab)
docker compose --profile minio up -d`}</CodeBlock>
              </div>
            </div>
            <div>
              <h3 className="font-display text-xl font-bold">GHCR images</h3>
              <div className="mt-4">
                <CodeBlock>{`export GHCR_OWNER=redmanxp
docker compose -f docker-compose.yml \\
  -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.yml \\
  -f docker-compose.ghcr.yml up -d`}</CodeBlock>
              </div>
              <p className="mt-3 text-sm text-ink/60">
                Images: <code className="rounded bg-mist px-1">mailarchive-api</code>,{" "}
                <code className="rounded bg-mist px-1">mailarchive-frontend</code>. Private packages
                need <code className="rounded bg-mist px-1">docker login ghcr.io</code>.
              </p>
            </div>
          </div>
        </section>

        {/* M365 */}
        <section id="microsoft365" className="border-y border-ink/10 bg-ink text-mist">
          <div className="section-pad mx-auto max-w-6xl py-24">
            <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Microsoft 365
            </h2>
            <p className="mt-3 max-w-2xl text-lg text-mist/80">
              Link mailboxes with Microsoft Graph OAuth. Tokens stay encrypted at rest — never store
              Microsoft passwords.
            </p>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {[
                ["OAuth link", "prompt=select_account; each link completes the credential flow."],
                ["Admin settings", "Configure client ID, tenant, secret, and redirect URI in the UI."],
                ["Archive & restore", "Manual, bulk, or scheduled incremental archive; restore to Graph."],
              ].map(([t, b]) => (
                <article key={t} className="rounded-3xl border border-white/10 bg-white/5 p-5">
                  <h3 className="font-display text-lg font-bold text-white">{t}</h3>
                  <p className="mt-2 text-mist/75">{b}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* IMAP */}
        <section id="imap" className="section-pad mx-auto max-w-6xl py-24">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">IMAP</h2>
          <p className="mt-3 max-w-2xl text-lg text-ink/70">
            Connect any IMAP server (including Gmail with an App Password). Test connection before
            saving; credentials are encrypted.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <article className="rounded-3xl border border-ink/10 bg-white p-6">
              <h3 className="font-display text-xl font-bold">What you configure</h3>
              <ul className="mt-4 space-y-2 text-ink/75">
                <li>Host, port, SSL</li>
                <li>Username / mailbox password (or App Password)</li>
                <li>Test button before link</li>
                <li>Reconnect from the Unlinked tab after soft-unlink</li>
              </ul>
            </article>
            <article className="rounded-3xl border border-ink/10 bg-teal/5 p-6">
              <h3 className="font-display text-xl font-bold">Gmail note</h3>
              <p className="mt-3 text-ink/75">
                Dedicated Gmail OAuth is deferred. Use IMAP + Google App Password for now — a UI
                preset is on the roadmap.
              </p>
            </article>
          </div>
        </section>

        {/* ROADMAP */}
        <section id="roadmap" className="border-y border-ink/10 bg-mist/50">
          <div className="section-pad mx-auto max-w-6xl py-24">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Roadmap</h2>
            <p className="mt-3 max-w-2xl text-lg text-ink/70">
              We say <strong>scheduled incremental archive</strong> — never “email sync”.
            </p>
            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              <article className="rounded-3xl border border-teal/30 bg-white p-6">
                <p className="text-xs font-bold uppercase tracking-wider text-teal">v1.0</p>
                <h3 className="mt-2 font-display text-xl font-bold">Shipped</h3>
                <ul className="mt-4 space-y-2 text-sm text-ink/75">
                  <li>Manual / bulk archive (M365 + IMAP)</li>
                  <li>FTS search, RBAC, audit</li>
                  <li>S3 storage, export, keep-copy restore</li>
                  <li>Scheduled incremental archive</li>
                  <li>Transfer / unlink / deactivate / purge</li>
                </ul>
              </article>
              <article className="rounded-3xl border border-ink/10 bg-white p-6">
                <p className="text-xs font-bold uppercase tracking-wider text-amber">v1.2</p>
                <h3 className="mt-2 font-display text-xl font-bold">Next</h3>
                <ul className="mt-4 space-y-2 text-sm text-ink/75">
                  <li>Employee departure archive flow</li>
                  <li>Retention policies UI</li>
                  <li>Optional Postgres</li>
                  <li>External job queue (Redis/Celery)</li>
                  <li>Gmail IMAP preset in UI</li>
                </ul>
              </article>
              <article className="rounded-3xl border border-ink/10 bg-white p-6">
                <p className="text-xs font-bold uppercase tracking-wider text-ink/50">v2.0</p>
                <h3 className="mt-2 font-display text-xl font-bold">Later</h3>
                <ul className="mt-4 space-y-2 text-sm text-ink/75">
                  <li>Legal hold / immutability</li>
                  <li>Deeper multi-tenant SaaS UX</li>
                </ul>
              </article>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="section-pad mx-auto max-w-6xl py-24">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">FAQ</h2>
          <div className="mt-10 space-y-4">
            {[
              [
                "Is MailArchive a mailbox sync tool?",
                "No. It is a self-hosted organizational archive. Scheduled jobs pull mail into local/S3 storage; they do not mirror deletes or bidirectional sync.",
              ],
              [
                "Do you store Microsoft passwords?",
                "Never. Microsoft 365 uses OAuth; tokens are encrypted at rest.",
              ],
              [
                "What happens when I unlink an account?",
                "Credentials are cleared (soft-unlink) and archived mail is kept by default. You can reconnect later or purge the archive with an explicit ELIMINAR confirmation.",
              ],
              [
                "Can I use S3 / MinIO?",
                "Yes. Configure object storage in Settings → Data. Branding stays on disk; mail objects can live in the bucket.",
              ],
              [
                "How can I support the project?",
                `Ko-fi: ${KOFI_PAGE} — every coffee helps.`,
              ],
            ].map(([q, a]) => (
              <details
                key={q}
                className="group rounded-2xl border border-ink/10 bg-white px-5 py-4 open:shadow-lift"
              >
                <summary className="cursor-pointer list-none font-display text-lg font-bold marker:content-none">
                  {q}
                </summary>
                <p className="mt-3 text-ink/70">{a}</p>
              </details>
            ))}
          </div>
          <div className="mt-14 flex flex-wrap items-center gap-4 rounded-3xl border border-ink/10 bg-gradient-to-br from-teal/10 to-amber/10 p-8">
            <div className="flex-1">
              <h3 className="font-display text-2xl font-bold">Support MailArchive</h3>
              <p className="mt-2 text-ink/70">
                Open source under MIT. If it helps your organization, buy us a coffee.
              </p>
            </div>
            <KofiButton />
            <a
              href={REPO}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-ink/20 bg-white px-4 py-2 text-sm font-semibold"
            >
              Star on GitHub
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-ink/10 bg-ink py-10 text-mist/70">
        <div className="section-pad mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <img src={asset("images/logo-icon.png")} alt="" className="h-8 w-8 rounded-md" />
            <span className="font-display font-bold text-white">MailArchive</span>
          </div>
          <p className="text-sm">MIT License · Self-hosted email archive</p>
          <div className="flex flex-wrap gap-3">
            <a href={REPO} className="text-sm hover:text-white">
              GitHub
            </a>
            <a href={KOFI_PAGE} className="text-sm hover:text-white">
              Ko-fi
            </a>
            <a href={MANUAL_EN} className="text-sm hover:text-white">
              Docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
