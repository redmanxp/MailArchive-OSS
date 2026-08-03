/** Etiquetas en castellano para valores técnicos de API. */

const ACCOUNT_STATUS: Record<string, string> = {
  pending: "Pendiente",
  connected: "Conectado",
  error: "Error",
  disconnected: "Desconectado",
};

const USER_STATUS: Record<string, string> = {
  active: "Activo",
  inactive: "Inactivo",
};

const JOB_STATUS: Record<string, string> = {
  pending: "Pendiente",
  running: "Archivando",
  completed: "Completado",
  failed: "Fallido",
  cancelled: "Cancelado",
  cancelling: "Cancelando",
};

const PROVIDER: Record<string, string> = {
  microsoft365: "Microsoft 365",
  imap: "IMAP",
  gmail: "Gmail",
};

const ROLE: Record<string, string> = {
  admin: "Administrador",
  supervisor: "Supervisor",
  user: "Usuario",
  readonly: "Solo lectura",
};

function label(map: Record<string, string>, value?: string | null, fallback?: string): string {
  if (!value) return fallback || "—";
  return map[value] || map[value.toLowerCase()] || value;
}

export function accountStatusLabel(value?: string | null) {
  return label(ACCOUNT_STATUS, value);
}

export function userStatusLabel(value?: string | null) {
  return label(USER_STATUS, value);
}

export function jobStatusLabel(value?: string | null) {
  return label(JOB_STATUS, value);
}

export function providerLabel(value?: string | null) {
  return label(PROVIDER, value);
}

export function roleLabel(value?: string | null) {
  return label(ROLE, value);
}
