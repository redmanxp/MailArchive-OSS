# MailArchive — Manual de usuario

URL: la que configure tu administrador (por ejemplo `https://mailarchive.example.com` o `http://localhost:8080` en lab).

> English version: [USER_MANUAL.md](./USER_MANUAL.md).  
> La interfaz y las plantillas de correo están en **español e inglés** (selector en Configuración → Idioma / preferencia de UI).

---

## Parte A — Usuarios

### 1. Primer acceso

1. Abrí la URL e iniciá sesión con tu **email** y **contraseña**.
2. **Organización (tenant / slug):**
   - En modo **single** (una sola organización, típico): el campo no se muestra.
   - En modo **multi**: tenés que indicar el slug de la organización.
3. Si el registro público está habilitado: en login, arriba a la derecha, **Crear usuario**.
   - Completá nombre, email y (si aplica) organización.
   - Te llega un correo con un enlace (válido 48 horas) para **definir tu contraseña**.
4. Si olvidaste la clave y el registro público está activo, usá otra vez **Crear usuario** con el mismo email: te llega un enlace de restablecimiento (no se duplica la cuenta).
5. Si el registro público está desactivado, pedí el alta a un administrador.
6. En el **primer acceso** o tras un invite, la app puede pedirte **cambiar la contraseña** (`must_change_password`).

### 2. Pantalla principal

Menú a la izquierda:

| Menú | Para qué sirve |
|------|----------------|
| Panel | Resumen: métricas, **salud del archivo** (jobs fallidos, schedules con error, último archivo), salud DB/storage |
| Cuentas | Vincular buzones (Microsoft 365 / IMAP) |
| Archivar | Archivar correos de a uno / puntuales |
| Masivo | Archivar muchos correos de una vez (con previsualización) |
| Archivados | Buscar, descargar y restaurar lo ya archivado |
| Usuarios | (Admin) Alta y edición de usuarios |
| Auditoría | (Admin / Supervisor) Registro de acciones |
| Configuración | (Admin) SMTP, plantillas, idioma, datos/storage, Microsoft, apariencia |
| Mi perfil | Click en tu nombre/email abajo a la izquierda |

### 3. Vincular una cuenta de correo

1. Andá a **Cuentas**.
2. Pulsá **+** y elegí:
   - **Microsoft 365**: OAuth completo (`select_account`). Usá la cuenta del buzón que querés archivar. **No** se guarda la contraseña de Microsoft; solo tokens cifrados.
   - **Gmail**: preset IMAP (`imap.gmail.com`, puerto 993, SSL). Usá una **contraseña de aplicación** de Google (no la contraseña normal de la cuenta).
   - **IMAP** genérico: host, puerto, SSL, usuario y contraseña; podés **Probar conexión** antes de guardar. La contraseña se cifra en reposo.
3. Podés vincular **varias** cuentas (M365 y/o IMAP).
4. Usuarios normales solo ven **sus** cuentas. Admin / Supervisor ven todas las del tenant (con dueño).
5. Pestañas **Activas** / **Desvinculadas**. En desvinculadas podés reconectar, purgar archivo (confirmación `ELIMINAR`) o borrar el vínculo si no hay archivados.
6. Icono de **reloj**: archivo programado **por cuenta** (no borra del proveedor). En el diálogo ves estado, última/próxima corrida y watermarks.
   - **Máximo por corrida** (1–2000, predeterminado 500): cuántos correos **nuevos** baja cada job. Los ya archivados no cuentan. **0 no descarga todo**.
   - **Archivar buzón histórico**: además de lo nuevo, cada corrida sigue hacia atrás hasta llenar ese cupo o hasta que no quede nada. El historial completo se completa en varias corridas (o con “Ejecutar ahora”).
   - Si no hay correo nuevo, usa el cupo entero para el histórico. Si el buzón ya está cubierto, el job termina rápido sin re-descargar.

### 4. Archivado masivo (lo más usado)

1. **Masivo** → elegí la cuenta y la carpeta (ej. Bandeja de entrada).
2. Opcional: rango de fechas, “más antiguos que X días”, solo con adjuntos, límite de cantidad (tope por job).
3. **Borrar del proveedor**: solo si querés que, después de archivar, se borren del Outlook/IMAP. **No está marcado por defecto**; confirmá con cuidado.
4. **Comenzar** → aparece “Preparando…” (podés **Cancelar** si tarda demasiado).
5. Revisá el listado: marcá o desmarcá correos, mirá el contenido si hace falta.
6. **Iniciar** el archivado.
7. El proceso sigue **en segundo plano**. Podés seguir usando la app; el avance se ve en **Procesos** (menú). Si hay jobs activos, aparece un reloj de arena con la cantidad.
8. Si un job **falla** o se **cancela**, podés **Reintentar** (mismo criterio). Si hay fallidos, el historial se abre solo.

Los correos ya archivados **no se pierden** si cancelás a mitad de camino. Los jobs en estado `pending` se retoman tras reiniciar la API; uno que estaba `running` al cortar el proceso queda marcado como fallido.

### 5. Correos archivados

En **Archivados**:

| Acción | Detalle |
|--------|---------|
| Buscar | Texto libre (full-text), remitente, cuenta, fechas, solo con adjuntos |
| Tabla | Asunto, **Cuenta**, De, fecha del mail, fecha de archivado, tamaño, adjuntos |
| Ver | Abrí el detalle (cuerpo HTML sanitizado, adjuntos descargables) |
| Descargar | EML individual o **ZIP** de varios seleccionados |
| Restaurar | Devuelve el mensaje al proveedor (carpeta MailArchive del buzón) o a **otra cuenta vinculada** |

#### Restaurar y mantener copia

Al restaurar (uno o varios) aparece el check **Mantener copia en la app** (**desactivado por defecto**) y el combo **Restaurar a**:

- **Cuenta original:** mismo buzón del que se archivó.
- **Otra cuenta:** usuario = solo las suyas; admin/supervisor = cualquier cuenta activa del tenant. Si el destino es distinto al origen, **siempre** se mantiene la copia en MailArchive.
- **Sin check** (solo cuenta original): restaura al proveedor y **elimina** el correo del archivo local.
- **Con check:** restaura al proveedor y **deja** la copia en MailArchive. Se marca la fecha de restauración.

### 6. Mi perfil

Click en tu nombre / email (abajo del menú): cambiar nombre o contraseña. El email de la cuenta no se cambia desde acá.

---

## Parte B — Administradores

### 7. Instalación inicial (una sola vez)

En la primera visita a una instalación vacía aparece el asistente:

| Campo | Ejemplo / notas |
|--------|-----------------|
| Nombre organización | `Demo` |
| Slug | `demo` (login multi; en single no se pide en login) |
| Modo tenant | **single** (una org) o **multi** |
| Motor DB | SQLite (lab) o MySQL |
| Carpeta de archivos | p. ej. `/storage` (EML + branding) |
| Nombre / email admin | `Admin Demo` / `admin@example.com` |
| Contraseña temporal | una clave segura |

Después iniciá sesión. Reiniciar el servidor **no** vuelve a abrir el install (queda en la base de datos).

### 8. Configuración (menú Admin)

#### 8.1 Correo saliente (SMTP)

Obligatorio para que los usuarios nuevos reciban el enlace de acceso.

- Servidor, puerto, usuario, contraseña, remitente (From), Reply-To, timeout, STARTTLS, habilitar.
- **Probar conexión** antes de guardar.

Sin SMTP, al crear un usuario la app puede crear la cuenta; si el mail falla, la UI muestra un **enlace copiable** (`setup_url`) para que el admin lo envíe a mano.

#### 8.2 Plantillas de email

Textos de **usuario nuevo** (invite) y **restablecimiento de contraseña**.

| Placeholder | Significado |
|-------------|-------------|
| `{name}` | Nombre del usuario |
| `{email}` | Email del usuario |
| `{tenant_slug}` | Organización |
| `{url}` | Enlace de set-password / reset |
| `{app_name}` | Nombre de la app |

Idioma base de plantillas (**es** / **en**) + personalización. Guardá al pie de Configuración.

#### 8.3 Idioma

Packs ES/EN para UI y correos. Afecta la interfaz de la sesión / preferencias de idioma.

#### 8.4 Datos y almacenamiento

| Opción | Qué hace |
|--------|----------|
| Carpeta de archivos | Raíz local (`STORAGE_ROOT`). Siempre usada para **branding**. |
| Backend | **Filesystem** (default) o **S3** compatible (MinIO, AWS, R2, Wasabi, …) |
| S3 | Endpoint, bucket, región, access/secret, path-style (recomendado MinIO), prefijo opcional |
| Motor DB | SQLite o MySQL (cambiar motor **requiere reinicio** de la API) |
| Modo tenant | single / multi (single no se puede si hay más de una organización) |

**Lab MinIO (Docker):** `docker compose --profile minio up -d` → en Datos usá endpoint `http://minio:9000`, usuario/clave `minioadmin`, bucket `mailarchive`, path-style activado.

Los correos ya archivados en disco **no migran solos** al pasar a S3.

Detalle operativo: [BACKUP.md](./BACKUP.md).

#### 8.5 Microsoft 365

Client ID, **Client secret (Value)**, tenant Azure, redirect URI.

- El redirect debe coincidir **exacto** con Azure (sin espacios).
- No pegues el **Secret ID** (GUID): hay que pegar el **Value** del secret.
- Redirect típico Docker UI: `http://localhost:8080/api/v1/accounts/microsoft/oauth/callback`

#### 8.6 Apariencia

Logo (icono / completo), nombre de marca y color primario. Reset a logos por defecto disponible.

### 9. Alta de usuarios y roles

1. **Usuarios** → **+** (formulario dedicado) con nombre, email y rol. Hay **filtro** por nombre/email/rol.
2. Preferí enviar email de bienvenida (SMTP + plantilla). Si falla el mail, copiá el enlace mostrado.
3. El usuario define contraseña con el enlace (48 h). **Nunca** se envía la contraseña en claro.
4. Pestañas **Activos** / **Desactivados**: reactivar o eliminar definitivo (sin borrar EML; reasigná cuentas si hace falta).
5. **Desactivar**: elegí transferir cuentas a otro usuario o desvincular (conserva archivo).
6. **Baja de empleado** (icono en Activos): opcionalmente archiva el histórico del buzón, desactiva schedules, transfiere o desvincula cuentas y desactiva el login. Si archivás, las cuentas deben **transferirse** (los jobs necesitan credenciales).

Roles internos (no son permisos de Microsoft):

| Rol | Acceso |
|-----|--------|
| Administrador | Todo el tenant: config, usuarios, todas las cuentas y correos |
| Supervisor | Ve todos los correos/cuentas del tenant; auditoría |
| Usuario | Sus cuentas y sus archivados |
| Solo lectura | Consulta sin archivar / restaurar |

### 10. Consejos rápidos

- Usá emails laborales reales: ahí llegan los enlaces.
- Antes de borrar del servidor de correo, asegurate de que el archivado terminó bien.
- Si un proceso masivo falla, revisá **Procesos**.
- ¿No llega el mail? Revisá SMTP, plantillas y spam; o usá el enlace copiable del alta.
- Para liberar cuota: archivá y marcá borrar del proveedor solo cuando el job terminó OK.
- Para backup operativo: restaurá con **Mantener copia en la app**, o dejá los EML en filesystem/S3 y respaldá según [BACKUP.md](./BACKUP.md).

### 11. Arranque rápido (Docker)

**Imágenes precompiladas (GHCR):**

```bash
cp .env.example .env
export GHCR_OWNER=redmanxp
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

**Build local:**

```bash
cp .env.example .env   # SECRET_KEY, JWT, DATA_ENCRYPTION_KEY, etc.
docker compose up --build
# UI http://localhost:8080 · API http://localhost:18100/health
```

- MySQL: `docker compose --profile mysql up --build` + `DB_ENGINE=mysql`
- MinIO: `docker compose --profile minio up -d`
- Resetear **datos** de lab (borra volúmenes): `docker compose down -v` — irreversible

Más: [README.md](../README.md) · [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) · [BACKUP.md](./BACKUP.md).
