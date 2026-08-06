/**
 * Label helpers for API enum values.
 * Prefer useLabels() so strings follow the active app locale.
 */
import { useLocale } from "../i18n/LocaleContext";

const FALLBACK_ACCOUNT_STATUS: Record<string, string> = {
  pending: "Pendiente",
  connected: "Conectado",
  error: "Error",
  disconnected: "Desconectado",
  unlinked: "Desvinculada",
};

const FALLBACK_USER_STATUS: Record<string, string> = {
  active: "Activo",
  inactive: "Inactivo",
};

const FALLBACK_JOB_STATUS: Record<string, string> = {
  pending: "Pendiente",
  running: "Archivando",
  completed: "Completado",
  failed: "Fallido",
  cancelled: "Cancelado",
  cancelling: "Cancelando",
};

const FALLBACK_PROVIDER: Record<string, string> = {
  microsoft365: "Microsoft 365",
  imap: "IMAP",
  gmail: "Gmail",
};

const FALLBACK_ROLE: Record<string, string> = {
  admin: "Administrador",
  supervisor: "Supervisor",
  user: "Usuario",
  readonly: "Solo lectura",
};

function pick(map: Record<string, string>, value?: string | null, fallback?: string): string {
  if (!value) return fallback || "—";
  return map[value] || map[value.toLowerCase()] || value;
}

/** Non-hook fallbacks (ES) for rare call sites outside LocaleProvider. */
export function accountStatusLabel(value?: string | null) {
  return pick(FALLBACK_ACCOUNT_STATUS, value);
}

export function userStatusLabel(value?: string | null) {
  return pick(FALLBACK_USER_STATUS, value);
}

export function jobStatusLabel(value?: string | null) {
  return pick(FALLBACK_JOB_STATUS, value);
}

export function providerLabel(value?: string | null) {
  return pick(FALLBACK_PROVIDER, value);
}

export function roleLabel(value?: string | null) {
  return pick(FALLBACK_ROLE, value);
}

export function useLabels() {
  const { t } = useLocale();
  const section = (sec: string, key: string, fb: string) => t(sec, key, fb);

  return {
    accountStatusLabel: (value?: string | null) =>
      value
        ? section("accountStatus", value, FALLBACK_ACCOUNT_STATUS[value] || value)
        : "—",
    userStatusLabel: (value?: string | null) =>
      value ? section("userStatus", value, FALLBACK_USER_STATUS[value] || value) : "—",
    jobStatusLabel: (value?: string | null) =>
      value ? section("jobStatus", value, FALLBACK_JOB_STATUS[value] || value) : "—",
    providerLabel: (value?: string | null) =>
      value ? section("provider", value, FALLBACK_PROVIDER[value] || value) : "—",
    roleLabel: (value?: string | null) =>
      value ? section("roles", value, FALLBACK_ROLE[value] || value) : "—",
  };
}
