/** Parse API datetimes. Backend stores UTC; naive ISO strings are treated as UTC. */
export function parseApiDate(value: string): Date {
  const s = value.trim();
  // Already has offset or Z
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)) {
    return new Date(s);
  }
  // Date only
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return new Date(`${s}T00:00:00Z`);
  }
  // Naive datetime from API → UTC
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(s)) {
    const normalized = s.includes("T") ? s : s.replace(" ", "T");
    return new Date(`${normalized}Z`);
  }
  return new Date(s);
}

/** Format ISO datetime for UI: browser local timezone. */
export function formatDateTime(value?: string | null, fallback = "—"): string {
  if (!value) return fallback;
  const d = parseApiDate(value);
  if (Number.isNaN(d.getTime())) return value;

  const date = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);

  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);

  return `${date} · ${time}`;
}

/** Compact for dense tables: dd/MM/yy HH:mm (local). */
export function formatDateTimeShort(value?: string | null, fallback = "—"): string {
  if (!value) return fallback;
  const d = parseApiDate(value);
  if (Number.isNaN(d.getTime())) return value;

  const date = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  }).format(d);

  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);

  return `${date} ${time}`;
}
