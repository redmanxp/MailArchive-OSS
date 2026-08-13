# MailArchive — User manual

URL: whatever your administrator configured (for example `https://mailarchive.example.com` or `http://localhost:8080` in a lab).

> Spanish version: [MANUAL_USUARIO.md](./MANUAL_USUARIO.md).  
> The UI and email templates support **Spanish and English** (Settings → Language / UI preference).

---

## Part A — Users

### 1. First sign-in

1. Open the URL and sign in with your **email** and **password**.
2. **Organization (tenant / slug):**
   - **Single** mode (one organization, typical): the field is hidden.
   - **Multi** mode: you must enter the organization slug.
3. If public registration is enabled: on the login screen, top right, **Create user**.
   - Enter name, email, and organization (when multi).
   - You receive an email with a link (valid 48 hours) to **set your password**.
4. If you forgot your password and public registration is on, use **Create user** again with the same email: you get a reset link (the account is not duplicated).
5. If public registration is disabled, ask an administrator to create your account.
6. On **first login** or after an invite, the app may require a **password change** (`must_change_password`).

### 2. Home screen

Left menu:

| Menu | Purpose |
|------|---------|
| Dashboard | Overview: metrics, **archive health** (failed jobs, schedule errors, last archive), DB/storage health |
| Accounts | Link mailboxes (Microsoft 365 / IMAP) |
| Archive | Archive individual / ad-hoc messages |
| Bulk | Archive many messages at once (with preview) |
| Archived | Search, download, and restore archived mail |
| Users | (Admin) Create and edit users |
| Audit | (Admin / Supervisor) Action log |
| Settings | (Admin) SMTP, templates, language, data/storage, Microsoft, appearance |
| My profile | Click your name/email at the bottom left |

### 3. Link a mailbox

1. Go to **Accounts**.
2. Press **+** and choose:
   - **Microsoft 365**: full OAuth (`select_account`) for the mailbox you want to archive. Microsoft passwords are **never** stored; tokens are encrypted at rest.
   - **Gmail**: IMAP preset (`imap.gmail.com`, port 993, SSL). Use a Google **App Password** (not the normal account password).
   - **Generic IMAP**: host, port, SSL, user, and password; you can **Test connection** before saving. The password is encrypted at rest.
3. You can link **multiple** accounts (M365 and/or IMAP).
4. Regular users only see **their** accounts. Admin / Supervisor see all tenant accounts (with owner).
5. Tabs **Active** / **Unlinked**. On unlinked you can reconnect, purge the archive (confirm `ELIMINAR` / DELETE), or remove the link if there are no archived messages.
6. **Clock** icon: **per-account** scheduled archive (does not delete from the provider). The dialog shows status, last/next run, and watermarks.
   - **Max messages per run** (1–2000, default 500): how many **new** messages each job archives. Already-archived mail does not count. **0 does not mean download everything**.
   - **Archive historical mailbox**: besides new mail, each run walks older messages until it fills that cap or the mailbox is exhausted. Full history takes multiple runs (or **Run now**).
   - If there is no new mail, the whole cap goes to history. If the mailbox is already covered, the job finishes quickly without re-downloading.

### 4. Bulk archive (most common)

1. **Bulk** → pick the account and folder (e.g. Inbox).
2. Optional: date range, “older than X days”, attachments only, quantity limit (per-job cap).
3. **Delete from provider**: only if you want messages removed from Outlook/IMAP after archiving. **Off by default**; confirm carefully.
4. **Start** → “Preparing…” (you can **Cancel** if it takes too long).
5. Review the list: select/deselect messages, preview if needed.
6. **Start** the archive job.
7. The job runs **in the background**. Progress is under **Jobs** in the menu. Active jobs show an hourglass badge with the count.
8. If a job **fails** or is **cancelled**, you can **Retry** (same criteria). Job history opens automatically when there are failures.

Messages already archived are **not lost** if you cancel mid-way. `pending` jobs survive an API restart; a job that was `running` when the process died is marked failed.

### 5. Archived mail

In **Archived**:

| Action | Detail |
|--------|--------|
| Search | Free text (full-text), sender, account, dates, attachments only |
| Table | Subject, **Account**, From, mail date, archived date, size, attachments |
| View | Open detail (sanitized HTML body, downloadable attachments) |
| Download | Single EML or **ZIP** of selected messages |
| Restore | Puts the message back on the provider (mailbox MailArchive folder) or **another linked account** |

#### Restore and keep a copy

When restoring (one or many), use **Keep a copy in the app** (**off by default**) and **Restore to**:

- **Original mailbox:** the account the message was archived from.
- **Another account:** users see only their own; admin/supervisor can pick any active tenant mailbox. A different destination **always** keeps the MailArchive copy.
- **Unchecked** (original mailbox only): restore to the provider and **remove** from the local archive.
- **Checked:** restore to the provider and **keep** the copy in MailArchive. A restored timestamp is recorded.

### 6. My profile

Click your name / email (bottom of the menu): change name or password. The account email cannot be changed here.

---

## Part B — Administrators

### 7. Initial install (once)

On the first visit to an empty install you see the wizard:

| Field | Example / notes |
|--------|-----------------|
| Organization name | `Demo` |
| Slug | `demo` (used in multi login; hidden in single) |
| Tenant mode | **single** (one org) or **multi** |
| Database | SQLite (lab) or MySQL |
| Storage folder | e.g. `/storage` (EML + branding) |
| Admin name / email | `Admin Demo` / `admin@example.com` |
| Temporary password | a strong password you will remember |

Then sign in. Restarting the server **does not** re-open install (it is stored in the database).

### 8. Settings (Admin menu)

#### 8.1 Outbound email (SMTP)

Required so new users receive the access link.

- Host, port, user, password, From, Reply-To, timeout, STARTTLS, enable.
- **Test connection** before saving.

Without SMTP, creating a user may still create the account; if email fails, the UI shows a **copyable link** (`setup_url`) for the admin to share manually.

#### 8.2 Email templates

Copy for **new user / invite** and **password reset**.

| Placeholder | Meaning |
|-------------|---------|
| `{name}` | User name |
| `{email}` | User email |
| `{tenant_slug}` | Organization |
| `{url}` | Set-password / reset link |
| `{app_name}` | App name |

Template language (**es** / **en**) plus customization. **Save** at the bottom of Settings.

#### 8.3 Language

ES/EN packs for UI and outbound mail.

#### 8.4 Data and storage

| Option | Purpose |
|--------|---------|
| Storage folder | Local root (`STORAGE_ROOT`). Always used for **branding**. |
| Backend | **Filesystem** (default) or **S3**-compatible (MinIO, AWS, R2, Wasabi, …) |
| S3 | Endpoint, bucket, region, access/secret, path-style (recommended for MinIO), optional prefix |
| Database | SQLite or MySQL (engine change **requires API restart**) |
| Tenant mode | single / multi (single is blocked if more than one organization exists) |

**MinIO lab (Docker):** `docker compose --profile minio up -d` → in Data use endpoint `http://minio:9000`, user/pass `minioadmin`, bucket `mailarchive`, path-style on.

Mail already archived on disk **does not auto-migrate** when switching to S3.

Ops detail: [BACKUP.md](./BACKUP.md).

#### 8.5 Microsoft 365

Client ID, **Client secret (Value)**, Azure tenant, redirect URI.

- Redirect must match Azure **exactly** (no trailing spaces).
- Do not paste the **Secret ID** (GUID); paste the secret **Value**.
- Typical Docker UI redirect: `http://localhost:8080/api/v1/accounts/microsoft/oauth/callback`

#### 8.6 Appearance

Logo (icon / full), brand name, and primary color. Reset to default logos is available.

### 9. Creating users and roles

1. **Users** → **+** (dedicated form) with name, email, and role. Use the **filter** by name/email/role when the list grows.
2. Prefer welcome email (SMTP + invite template). If mail fails, copy the link shown in the UI.
3. The user sets a password via the 48h link. A cleartext password is **never** emailed.
4. Tabs **Active** / **Deactivated**: reactivate or permanently delete (archive EML is kept; reassign accounts first if needed).
5. **Deactivate**: choose transfer accounts to another user, or unlink (keep archive).
6. **Employee departure** (icon on Active): optionally archive mailbox history, disable schedules, transfer or unlink accounts, and deactivate login. When archiving, accounts must be **transferred** (jobs need credentials).

Internal roles (not Microsoft permissions):

| Role | Access |
|------|--------|
| Administrator | Full tenant: settings, users, all accounts and mail |
| Supervisor | All tenant mail/accounts; audit |
| User | Own accounts and archived mail |
| Read-only | View without archive / restore |

### 10. Quick tips

- Use real work emails: that is where links arrive.
- Before deleting from the mail server, ensure the archive job finished successfully.
- If a bulk job fails, check **Jobs**.
- Mail not arriving? Check SMTP, templates, and spam — or use the copyable invite link.
- To free quota: archive and only then delete from the provider after a successful job.
- For operational backup: restore with **Keep a copy in the app**, or back up EML on filesystem/S3 per [BACKUP.md](./BACKUP.md).

### 11. Quick start (Docker)

**Pre-built images (GHCR):**

```bash
cp .env.example .env
export GHCR_OWNER=redmanxp
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

**Build from source:**

```bash
cp .env.example .env   # SECRET_KEY, JWT, DATA_ENCRYPTION_KEY, etc.
docker compose up --build
# UI http://localhost:8080 · API http://localhost:18100/health
```

- MySQL: `docker compose --profile mysql up --build` + `DB_ENGINE=mysql`
- MinIO: `docker compose --profile minio up -d`
- Reset **lab data** (deletes volumes): `docker compose down -v` — irreversible

More: [README.md](../README.md) · [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) · [BACKUP.md](./BACKUP.md).
