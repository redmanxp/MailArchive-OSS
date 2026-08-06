/** Default and API branding logo helpers. */
export type LogoKind = "icon" | "full";

const DEFAULTS: Record<LogoKind, string> = {
  icon: "/branding/logo-icon.png",
  full: "/branding/logo-full.png",
};

/** API URL that serves custom logo or built-in default. */
export function brandingApiUrl(kind: LogoKind, cacheBust?: number | string): string {
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  const q = cacheBust != null ? `?v=${cacheBust}` : "";
  return `${base}/api/v1/branding/logo/${kind}${q}`;
}

export function brandingFallbackUrl(kind: LogoKind): string {
  return DEFAULTS[kind];
}
