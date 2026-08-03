# Seguridad — MailArchive

## Regla de oro

**Nunca subir secretos a GitHub** (ni a ningún remoto).

## Qué NO versionar

- `.env` y variantes (excepto `.env.example`)
- Passwords (MySQL, SMTP, IMAP)
- `MICROSOFT_CLIENT_SECRET` y tokens OAuth
- Claves (`*.pem`, `*.key`, Fernet keys reales)
- Contenido de `storage/` (correos, adjuntos, metadata real)
- Dumps SQL / backups con datos

## Qué SÍ versionar

- `.env.example` con placeholders vacíos o `change-me-...`
- Documentación de variables requeridas
- Código y migraciones sin credenciales embebidas

## Si se filtró un secreto

1. Rotar el secreto de inmediato (Azure AD, DB, SMTP, etc.).
2. Revocar tokens afectados.
3. Si ya se pusheó a GitHub: tratar el commit como comprometido; limpiar historial o rotar y asumir exposición.
4. Avisar al responsable del proyecto.
