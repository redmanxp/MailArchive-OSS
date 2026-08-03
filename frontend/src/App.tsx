import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import { getInstallStatus } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import DashboardPage from "./pages/DashboardPage";
import InstallPage from "./pages/InstallPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SetPasswordPage from "./pages/SetPasswordPage";
import ProfilePage from "./pages/ProfilePage";
import AccountsPage from "./pages/AccountsPage";
import ArchivePage from "./pages/ArchivePage";
import BulkArchivePage from "./pages/BulkArchivePage";
import BulkPreviewPage from "./pages/BulkPreviewPage";
import MailsPage from "./pages/MailsPage";
import UsersPage from "./pages/UsersPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import SettingsPage from "./pages/SettingsPage";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, loading } = useAuth();
  const [installed, setInstalled] = useState<boolean | null>(null);

  useEffect(() => {
    getInstallStatus()
      .then((s) => setInstalled(s.installed))
      .catch(() => setInstalled(false));
  }, []);

  if (installed === null || loading) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!installed) {
    return <InstallPage onInstalled={() => setInstalled(true)} />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user && !user.must_change_password ? <Navigate to="/app" replace /> : <LoginPage />}
      />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/set-password" element={<SetPasswordPage />} />
      <Route
        path="/change-password"
        element={user ? <ChangePasswordPage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/app"
        element={
          <Protected>
            <DashboardPage />
          </Protected>
        }
      />
      <Route
        path="/app/profile"
        element={
          <Protected>
            <ProfilePage />
          </Protected>
        }
      />
      <Route
        path="/app/accounts"
        element={
          <Protected>
            <AccountsPage />
          </Protected>
        }
      />
      <Route
        path="/app/archive"
        element={
          <Protected>
            <ArchivePage />
          </Protected>
        }
      />
      <Route
        path="/app/bulk"
        element={
          <Protected>
            <BulkArchivePage />
          </Protected>
        }
      />
      <Route
        path="/app/bulk/preview"
        element={
          <Protected>
            <BulkPreviewPage />
          </Protected>
        }
      />
      <Route
        path="/app/mails"
        element={
          <Protected>
            <MailsPage />
          </Protected>
        }
      />
      <Route
        path="/app/users"
        element={
          <Protected>
            <AdminOnly>
              <UsersPage />
            </AdminOnly>
          </Protected>
        }
      />
      <Route
        path="/app/audit"
        element={
          <Protected>
            <AdminOnly>
              <AuditLogsPage />
            </AdminOnly>
          </Protected>
        }
      />
      <Route
        path="/app/settings"
        element={
          <Protected>
            <AdminOnly>
              <SettingsPage />
            </AdminOnly>
          </Protected>
        }
      />
      <Route
        path="*"
        element={
          <Navigate
            to={user ? (user.must_change_password ? "/change-password" : "/app") : "/login"}
            replace
          />
        }
      />
    </Routes>
  );
}
