/** Format ISO datetime for UI: local timezone, date and time readable in one field. */

export function formatDateTime(value?: string | null, fallback = "—"): string {
  if (!value) return fallback;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;

  const date = new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);

  const time = new Intl.DateTimeFormat("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);

  return `${date} · ${time}`;
}

/** Compact for dense tables: dd/MM/yy HH:mm */
export function formatDateTimeShort(value?: string | null, fallback = "—"): string {
  if (!value) return fallback;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;

  const date = new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  }).format(d);

  const time = new Intl.DateTimeFormat("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);

  return `${date} ${time}`;
}
