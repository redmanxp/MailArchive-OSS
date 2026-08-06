# MailArchive — Manual de usuario

URL: la que configure tu administrador (por ejemplo `https://mailarchive.example.com`).

> English version: [USER_MANUAL.md](./USER_MANUAL.md).  
> La interfaz y las plantillas de correo ya están preparadas para multi-idioma (ES/EN); la UI completa i18n llega en una fase siguiente.

---

## Parte A — Usuarios

### 1. Primer acceso

1. Entrá a la URL e iniciá sesión con tu **email** y la **organización** (tenant / slug).
2. Si el registro público está habilitado: en login, arriba a la derecha, **Crear usuario**.
   - Completá nombre, email y organización.
   - Te llega un correo con un enlace (válido 48 horas) para **definir tu contraseña**.
3. Si olvidaste la clave y el registro público está activo, usá otra vez **Crear usuario** con el mismo email: te llega un enlace de restablecimiento (no se duplica la cuenta).
4. Si el registro público está desactivado, pedí el alta a un administrador.

### 2. Pantalla principal

Menú a la izquierda:

| Menú | Para qué sirve |
|------|----------------|
| Panel | Resumen general |
| Cuentas | Vincular buzones (Outlook / IMAP) |
| Archivar | Archivar correos de a uno / puntuales |
| Masivo | Archivar muchos correos de una vez |
| Archivados | Buscar y usar lo ya archivado |
| Mi perfil | Click en tu nombre/email abajo a la izquierda |

### 3. Vincular una cuenta de correo

1. Andá a **Cuentas**.
2. Pulsá **+** y elegí:
   - **Microsoft 365**: te lleva a iniciar sesión en Microsoft. Usá la cuenta del buzón que querés archivar.
   - **IMAP**: cargá servidor, puerto, usuario y contraseña; podés **Probar conexión** antes de guardar.
3. Solo ves y administrás **tus** cuentas.

### 4. Archivado masivo (lo más usado)

1. **Masivo** → elegí la cuenta y la carpeta (ej. Bandeja de entrada).
2. Opcional: fechas, “más antiguos que X días”, solo con adjuntos, límite de cantidad.
3. **Borrar del proveedor**: solo si querés que, después de archivar, se borren del Outlook/IMAP. **No está marcado por defecto**; confirmá con cuidado.
4. **Comenzar** → aparece “Preparando…” (podés **Cancelar** si tarda demasiado).
5. Revisá el listado: marcá o desmarcá correos, mirá el contenido si hace falta.
6. **Iniciar** el archivado.
7. El proceso sigue **en segundo plano**. Podés seguir usando la app; el avance se ve en **Procesos en curso** (Masivo).

Los correos ya archivados **no se pierden** si cancelás a mitad de camino.

### 5. Correos archivados

En **Archivados** podés filtrar, abrir, descargar (ZIP) y **restaurar** al buzón original.

### 6. Mi perfil

Click en tu nombre / email (abajo del menú): cambiar nombre o contraseña. El email de la cuenta no se cambia desde acá.

---

## Parte B — Administradores

### 7. Instalación inicial (una sola vez)

En la primera visita a una instalación vacía aparece el asistente:

| Campo | Ejemplo |
|--------|---------|
| Nombre tenant | `Demo` |
| Slug tenant | `demo` |
| Nombre admin | `Admin Demo` |
| Email admin | `admin@example.com` |
| Contraseña temporal | una clave segura que recuerdes |

Después usá ese slug + email + contraseña en el login. Reiniciar el servidor **no** vuelve a abrir el install (queda marcado en la base de datos).

### 8. Configuración (menú Admin)

La pantalla **Configuración** está segmentada:

#### 8.1 Correo saliente (SMTP)

Obligatorio para que los usuarios nuevos reciban el enlace de acceso.

- Servidor, puerto, usuario, contraseña, remitente (From), STARTTLS, habilitar.
- **Probar conexión** antes de guardar.
- Sirve cualquier SMTP (Microsoft 365, Google Workspace, relay propio, etc.).

Sin SMTP configurado, al crear un usuario la app puede crear la cuenta pero el correo no se envía.

#### 8.2 Plantillas de email

Textos del mensaje que recibe un **usuario nuevo** (invite) y del **restablecimiento de contraseña**.

Placeholders disponibles:

| Placeholder | Significado |
|-------------|-------------|
| `{name}` | Nombre del usuario |
| `{email}` | Email del usuario |
| `{tenant_slug}` | Organización |
| `{url}` | Enlace de set-password / reset |
| `{app_name}` | Nombre remitente / app |

Campos por plantilla: asunto, saludo, intro, texto del botón, pie, texto si el botón no funciona.

Podés elegir idioma base de plantillas (**es** / **en**) y luego personalizar el texto. Guardá con el botón **Guardar** al pie de Configuración.

#### 8.3 Apariencia

Reservado para logo y colores de la organización (próximamente).

### 9. Alta de usuarios

1. **Usuarios** → crear con nombre, email y rol.
2. Preferí **enviar email de bienvenida** (usa SMTP + plantilla invite).
3. El usuario define contraseña con el enlace (48 h). **Nunca** se envía la contraseña en claro si usás el flujo por enlace.

### 10. Consejos rápidos

- Usá emails laborales reales: ahí llegan los enlaces.
- Antes de borrar del servidor de correo, asegurate de que el archivado terminó bien.
- Si un proceso masivo falla, revisá **Procesos en curso**.
- ¿No llega el mail? Revisá SMTP, plantillas y carpeta de spam; avisá al admin de MailArchive.
