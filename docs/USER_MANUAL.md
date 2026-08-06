# MailArchive — User manual

URL: whatever your administrator configured (for example `https://mailarchive.example.com`).

> Spanish version: [MANUAL_USUARIO.md](./MANUAL_USUARIO.md).  
> The UI and email templates are prepared for ES/EN; full UI i18n comes in a later phase.

---

## Part A — Users

### 1. First sign-in

1. Open the URL and sign in with your **email** and **organization** (tenant / slug).
2. If public registration is enabled: on the login screen, top right, **Create user**.
   - Enter name, email, and organization.
   - You receive an email with a link (valid 48 hours) to **set your password**.
3. If you forgot your password and public registration is on, use **Create user** again with the same email: you get a reset link (the account is not duplicated).
4. If public registration is disabled, ask an administrator to create your account.

### 2. Home screen

Left menu:

| Menu | Purpose |
|------|---------|
| Dashboard | Overview |
| Accounts | Link mailboxes (Outlook / IMAP) |
| Archive | Archive individual / ad-hoc messages |
| Bulk | Archive many messages at once |
| Archived | Search and use already archived mail |
| My profile | Click your name/email at the bottom left |

### 3. Link a mailbox

1. Go to **Accounts**.
2. Press **+** and choose:
   - **Microsoft 365**: sign in with Microsoft for the mailbox you want to archive.
   - **IMAP**: enter host, port, user, and password; you can **Test connection** before saving.
3. You only see and manage **your** accounts.

### 4. Bulk archive (most common)

1. **Bulk** → pick the account and folder (e.g. Inbox).
2. Optional: date range, “older than X days”, attachments only, quantity limit.
3. **Delete from provider**: only if you want messages removed from Outlook/IMAP after archiving. **Off by default**; confirm carefully.
4. **Start** → “Preparing…” (you can **Cancel** if it takes too long).
5. Review the list: select/deselect messages, preview if needed.
6. **Start** the archive job.
7. The job runs **in the background**. Progress is under **Jobs in progress** (Bulk).

Messages already archived are **not lost** if you cancel mid-way.

### 5. Archived mail

In **Archived** you can filter, open, download (ZIP), and **restore** to the original mailbox.

### 6. My profile

Click your name / email (bottom of the menu): change name or password. The account email cannot be changed here.

---

## Part B — Administrators

### 7. Initial install (once)

On the first visit to an empty install you see the wizard:

| Field | Example |
|--------|---------|
| Tenant name | `Demo` |
| Tenant slug | `demo` |
| Admin name | `Admin Demo` |
| Admin email | `admin@example.com` |
| Temporary password | a strong password you will remember |

Then sign in with that slug + email + password. Restarting the server **does not** re-open install (it is stored in the database).

### 8. Settings (Admin menu)

**Settings** is split into sections:

#### 8.1 Outbound email (SMTP)

Required so new users receive the access link.

- Host, port, user, password, From address, STARTTLS, enable.
- **Test connection** before saving.
- Any SMTP works (Microsoft 365, Google Workspace, self-hosted relay, etc.).

Without SMTP, creating a user may still create the account but the email will not be sent.

#### 8.2 Email templates

Copy for **new user / invite** and **password reset** messages.

Placeholders:

| Placeholder | Meaning |
|-------------|---------|
| `{name}` | User name |
| `{email}` | User email |
| `{tenant_slug}` | Organization |
| `{url}` | Set-password / reset link |
| `{app_name}` | From name / app name |

Per template: subject, greeting, intro, button label, footer, fallback if the button fails.

Choose template language (**es** / **en**), customize text, then **Save** at the bottom of Settings.

#### 8.3 Appearance

Reserved for organization logo and colors (coming soon).

### 9. Creating users

1. **Users** → create with name, email, and role.
2. Prefer **send welcome email** (uses SMTP + invite template).
3. The user sets a password via the 48h link. A cleartext password is **never** emailed when using the link flow.

### 10. Quick tips

- Use real work emails: that is where links arrive.
- Before deleting from the mail server, ensure the archive job finished successfully.
- If a bulk job fails, check **Jobs in progress**.
- Mail not arriving? Check SMTP, templates, and spam; contact the MailArchive admin.
