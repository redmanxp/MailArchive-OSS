/**
 * Lightweight i18n catalog for UI strings (Spanish defaults).
 *
 * Prep for a full library (e.g. react-i18next): keep message keys stable and
 * add locales under this folder. Pages should call `t()` instead of hard-coding.
 */
export const messages = {
  settings: {
    title: "Configuración",
    subtitle: "Correo saliente, plantillas de mensajes y apariencia de la organización.",
    sectionSmtp: "Correo saliente (SMTP)",
    sectionSmtpHint:
      "Servidor usado para enviar el enlace de acceso a usuarios nuevos y restablecimientos de contraseña. Cualquier SMTP (Microsoft 365, Google, relay propio, etc.).",
    sectionTemplates: "Plantillas de email",
    sectionTemplatesHint:
      "Textos del correo de bienvenida / invite y del restablecimiento. Placeholders: {name}, {email}, {tenant_slug}, {url}, {app_name}.",
    sectionAppearance: "Apariencia",
    sectionAppearanceHint: "Logo, nombre de marca y color primario de la organización.",
    appearanceSoon: "Subí logos personalizados en Configuración → Apariencia.",
    host: "Servidor SMTP",
    port: "Puerto",
    user: "Usuario (email completo)",
    password: "Contraseña SMTP",
    passwordHint: "Dejar vacío para no cambiar la guardada.",
    fromEmail: "Remitente (From)",
    fromName: "Nombre remitente",
    starttls: "STARTTLS (puerto 587)",
    enabled: "SMTP habilitado",
    test: "Probar conexión",
    save: "Guardar",
    saved: "Configuración guardada.",
    testOk: "Conexión SMTP OK",
    locale: "Idioma de las plantillas",
    inviteTitle: "Nuevo usuario / invite",
    resetTitle: "Restablecer contraseña",
    subject: "Asunto",
    greeting: "Saludo",
    intro: "Cuerpo (introducción)",
    buttonLabel: "Texto del botón",
    footer: "Pie",
    linkFallback: "Texto si el botón no funciona",
    loading: "Cargando…",
  },
} as const;

export type Messages = typeof messages;
