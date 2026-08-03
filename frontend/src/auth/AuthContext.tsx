import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  changePassword as apiChangePassword,
  login as apiLogin,
  logout as apiLogout,
  me,
  type UserPublic,
} from "../api/client";

type AuthState = {
  user: UserPublic | null;
  loading: boolean;
  login: (email: string, password: string, tenantSlug?: string) => Promise<UserPublic>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const token = localStorage.getItem("ma_access_token");
    if (!token) {
      setUser(null);
      return;
    }
    const profile = await me();
    setUser(profile);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refreshMe();
      } catch {
        localStorage.removeItem("ma_access_token");
        localStorage.removeItem("ma_refresh_token");
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string, tenantSlug?: string) => {
    const data = await apiLogin(email, password, tenantSlug);
    localStorage.setItem("ma_access_token", data.access_token);
    localStorage.setItem("ma_refresh_token", data.refresh_token);
    const profile = data.user ?? (await me());
    setUser(profile);
    return profile;
  }, []);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    await apiChangePassword(currentPassword, newPassword);
    localStorage.removeItem("ma_access_token");
    localStorage.removeItem("ma_refresh_token");
    setUser(null);
  }, []);

  const logout = useCallback(async () => {
    const refresh = localStorage.getItem("ma_refresh_token");
    try {
      if (refresh) await apiLogout(refresh);
    } finally {
      localStorage.removeItem("ma_access_token");
      localStorage.removeItem("ma_refresh_token");
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, changePassword, logout, refreshMe }),
    [user, loading, login, changePassword, logout, refreshMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
