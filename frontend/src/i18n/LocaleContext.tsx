/**
 * App-wide locale context: loads language packs from the API.
 * Packs are JSON files on the server; adding a new file exposes it in the Language tab.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import axios from "axios";

const apiBase = import.meta.env.VITE_API_URL || "";

export type LocaleOption = { code: string; name: string };

type LocalePack = {
  code: string;
  name: string;
  ui: Record<string, any>;
  email: Record<string, any>;
};

type LocaleContextValue = {
  locale: string;
  locales: LocaleOption[];
  ui: Record<string, any>;
  loading: boolean;
  setLocale: (code: string) => Promise<void>;
  /** Nested lookup: t("settings", "title") or t("nav", "dashboard") */
  t: (section: string, key: string, fallback?: string) => string;
  /** Replace `{name}` placeholders in a translated string. */
  tf: (section: string, key: string, vars: Record<string, string | number>, fallback?: string) => string;
  reload: () => Promise<void>;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

const STORAGE_KEY = "ma_ui_locale";

async function fetchLocales(): Promise<LocaleOption[]> {
  const { data } = await axios.get<{ locales: LocaleOption[] }>(`${apiBase}/api/v1/i18n/locales`, {
    timeout: 10000,
  });
  return data.locales || [];
}

async function fetchPack(code: string): Promise<LocalePack> {
  const { data } = await axios.get<LocalePack>(`${apiBase}/api/v1/i18n/${encodeURIComponent(code)}`, {
    timeout: 10000,
  });
  return data;
}

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: string;
}) {
  const [locales, setLocales] = useState<LocaleOption[]>([]);
  const [locale, setLocaleState] = useState(initialLocale || localStorage.getItem(STORAGE_KEY) || "es");
  const [ui, setUi] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (code: string) => {
    setLoading(true);
    try {
      const [list, pack] = await Promise.all([fetchLocales(), fetchPack(code)]);
      setLocales(list);
      const resolved =
        list.find((l) => l.code === code)?.code || list[0]?.code || pack.code || "es";
      if (resolved !== code) {
        const pack2 = await fetchPack(resolved);
        setLocaleState(resolved);
        setUi(pack2.ui || {});
        localStorage.setItem(STORAGE_KEY, resolved);
      } else {
        setLocaleState(resolved);
        setUi(pack.ui || {});
        localStorage.setItem(STORAGE_KEY, resolved);
      }
    } catch {
      setUi({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(locale);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only once on mount
  }, []);

  useEffect(() => {
    if (initialLocale && initialLocale !== locale) {
      void load(initialLocale);
    }
  }, [initialLocale]); // eslint-disable-line react-hooks/exhaustive-deps

  const setLocale = useCallback(
    async (code: string) => {
      await load(code);
    },
    [load]
  );

  const t = useCallback(
    (section: string, key: string, fallback = "") => {
      const value = ui?.[section]?.[key];
      return typeof value === "string" && value.length ? value : fallback || key;
    },
    [ui]
  );

  const tf = useCallback(
    (section: string, key: string, vars: Record<string, string | number>, fallback = "") => {
      let s = t(section, key, fallback);
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
      return s;
    },
    [t]
  );

  const value = useMemo(
    () => ({
      locale,
      locales,
      ui,
      loading,
      setLocale,
      t,
      tf,
      reload: () => load(locale),
    }),
    [locale, locales, ui, loading, setLocale, t, tf, load]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
