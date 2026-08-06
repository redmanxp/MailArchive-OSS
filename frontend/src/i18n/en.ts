/**
 * English UI catalog — keep keys in sync with `./es.ts`.
 */
export const messages = {
  settings: {
    title: "Settings",
    subtitle: "Outbound mail, message templates, and organization appearance.",
    sectionSmtp: "Outbound email (SMTP)",
    sectionSmtpHint:
      "Server used to send access links to new users and password resets. Any SMTP relay works.",
    sectionTemplates: "Email templates",
    sectionTemplatesHint:
      "Invite/welcome and password-reset copy. Placeholders: {name}, {email}, {tenant_slug}, {url}, {app_name}.",
    sectionAppearance: "Appearance",
    sectionAppearanceHint: "Logo, brand name, and primary color for the organization.",
    appearanceSoon: "Upload custom logos under Settings → Appearance.",
    host: "SMTP host",
    port: "Port",
    user: "Username (full email)",
    password: "SMTP password",
    passwordHint: "Leave blank to keep the stored password.",
    fromEmail: "From address",
    fromName: "From name",
    starttls: "STARTTLS (port 587)",
    enabled: "SMTP enabled",
    test: "Test connection",
    save: "Save",
    saved: "Settings saved.",
    testOk: "SMTP connection OK",
    locale: "Template language",
    inviteTitle: "New user / invite",
    resetTitle: "Password reset",
    subject: "Subject",
    greeting: "Greeting",
    intro: "Body (intro)",
    buttonLabel: "Button label",
    footer: "Footer",
    linkFallback: "Fallback if the button fails",
    loading: "Loading…",
  },
} as const;
