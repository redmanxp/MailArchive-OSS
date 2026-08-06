/**
 * Default invite/reset email bodies for the settings editor.
 * Keep in sync with backend `app.infrastructure.email.templates.DEFAULT_TEMPLATES`.
 */
import type { EmailTemplates } from "../api/client";

export function defaultEmailTemplates(locale: string): EmailTemplates {
  const loc = locale === "en" ? "en" : "es";
  if (loc === "en") {
    return {
      locale: "en",
      invite: {
        subject: "Access to {app_name}",
        greeting: "Hello {name},",
        intro:
          "Your {app_name} account was created (organization: {tenant_slug}). Click the button to set your password. The link is valid for 48 hours.",
        button_label: "Set password",
        footer: "Email: {email}. If you did not request this, ignore this message.",
        link_fallback: "If the button does not work, copy this link:",
      },
      reset: {
        subject: "Reset password — {app_name}",
        greeting: "Hello {name},",
        intro:
          "We received a request to reset your {app_name} password. Click the button to choose a new one (valid for 48 hours).",
        button_label: "Reset password",
        footer: "Email: {email}. If this was not you, ignore this message.",
        link_fallback: "If the button does not work, copy this link:",
      },
    };
  }
  return {
    locale: "es",
    invite: {
      subject: "Acceso a {app_name}",
      greeting: "Hola {name},",
      intro:
        "Se creó tu usuario en {app_name} (organización: {tenant_slug}). Hacé clic en el botón para definir tu contraseña. El enlace vale 48 horas.",
      button_label: "Definir contraseña",
      footer: "Email: {email}. Si no solicitaste esto, ignorá el mensaje.",
      link_fallback: "Si el botón no funciona, copiá este enlace:",
    },
    reset: {
      subject: "Restablecer contraseña — {app_name}",
      greeting: "Hola {name},",
      intro:
        "Recibimos un pedido para restablecer tu contraseña de {app_name}. Hacé clic en el botón para elegir una nueva (válido 48 horas).",
      button_label: "Restablecer contraseña",
      footer: "Email: {email}. Si no fuiste vos, ignorá este mensaje.",
      link_fallback: "Si el botón no funciona, copiá este enlace:",
    },
  };
}
