# Security — MailArchive

## Golden rule

**Never commit secrets to GitHub** (or any remote).

## Reporting vulnerabilities

Open a [GitHub Security Advisory](https://github.com/redmanxp/MailArchive-OSS/security/advisories/new) on this repository, or contact the project maintainer. Do not publish exploits in public issues until a fix is available.

## Do not version

- `.env` and variants (except `.env.example`)
- Passwords (MySQL, SMTP, IMAP)
- `MICROSOFT_CLIENT_SECRET` and OAuth tokens
- Keys (`*.pem`, `*.key`, real Fernet keys)
- Contents of `storage/` (mail, attachments, real metadata)
- SQL dumps / backups with real data

## Do version

- `.env.example` with empty placeholders or `change-me-...`
- Documentation of required variables
- Code and migrations without embedded credentials

## If a secret was leaked

1. Rotate the secret immediately (Azure AD, DB, SMTP, etc.).
2. Revoke affected tokens.
3. If it was already pushed to GitHub: treat the commit as compromised; scrub history or rotate and assume exposure.
4. Notify the project maintainer.
