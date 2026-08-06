/**
 * Initial install — organization, admin, and data location (DB / storage).
 */
import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Container,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { getInstallStatus, installApp } from "../api/client";
import BrandLogo from "../components/BrandLogo";
import { useLocale } from "../i18n/LocaleContext";

type Props = {
  onInstalled: () => void;
};

export default function InstallPage({ onInstalled }: Props) {
  const { t } = useLocale();
  const [tenantName, setTenantName] = useState("Acme");
  const [tenantSlug, setTenantSlug] = useState("acme");
  const [adminName, setAdminName] = useState("Administrator");
  const [adminEmail, setAdminEmail] = useState("admin@example.com");
  const [adminPassword, setAdminPassword] = useState("");
  const [dbEngine, setDbEngine] = useState("sqlite");
  const [storageRoot, setStorageRoot] = useState("/storage");
  const [mysqlHost, setMysqlHost] = useState("127.0.0.1");
  const [mysqlPort, setMysqlPort] = useState(3306);
  const [mysqlUser, setMysqlUser] = useState("mailarchive");
  const [mysqlDatabase, setMysqlDatabase] = useState("mailarchive");
  const [mysqlPassword, setMysqlPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getInstallStatus()
      .then((s) => {
        if (s.db_engine) setDbEngine(s.db_engine);
        if (s.storage_root) setStorageRoot(s.storage_root);
        if (s.restart_required) setInfo(t("install", "restartHint"));
      })
      .catch(() => undefined);
  }, [t]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await installApp({
        tenant_name: tenantName,
        tenant_slug: tenantSlug,
        admin_name: adminName,
        admin_email: adminEmail,
        admin_password: adminPassword || undefined,
        storage_root: storageRoot || undefined,
        db_engine: dbEngine,
        mysql_host: dbEngine === "mysql" ? mysqlHost : undefined,
        mysql_port: dbEngine === "mysql" ? mysqlPort : undefined,
        mysql_user: dbEngine === "mysql" ? mysqlUser : undefined,
        mysql_database: dbEngine === "mysql" ? mysqlDatabase : undefined,
        mysql_password: dbEngine === "mysql" ? mysqlPassword || undefined : undefined,
      });
      onInstalled();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        t("install", "failed");
      if (status === 409) {
        setInfo(String(msg));
      } else {
        setError(String(msg));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background:
          "radial-gradient(circle at top left, #d7e8f3 0%, #f3f6f8 45%, #e8eef2 100%)",
        px: 2,
        py: 4,
      }}
    >
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: 4, border: "1px solid #d5dee5" }}>
          <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
            <BrandLogo kind="full" height={140} maxWidth={280} />
          </Box>
          <Typography color="text.secondary" sx={{ mb: 3, textAlign: "center" }}>
            {t("install", "subtitle")}
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          {info && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {info}
            </Alert>
          )}
          <Stack component="form" spacing={2} onSubmit={onSubmit}>
            <Typography variant="subtitle2">{t("install", "sectionOrg")}</Typography>
            <TextField label={t("install", "tenantName")} value={tenantName} onChange={(e) => setTenantName(e.target.value)} required />
            <TextField label={t("install", "tenantSlug")} value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} required />
            <TextField label={t("install", "adminName")} value={adminName} onChange={(e) => setAdminName(e.target.value)} required />
            <TextField label={t("install", "adminEmail")} type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required />
            <TextField
              label={t("install", "adminPassword")}
              type="password"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              helperText={t("install", "passwordHint")}
              required
              autoComplete="new-password"
            />

            <Typography variant="subtitle2" sx={{ pt: 1 }}>
              {t("install", "sectionData")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("install", "sectionDataHint")}
            </Typography>
            <TextField
              select
              label={t("install", "dbEngine")}
              value={dbEngine}
              onChange={(e) => setDbEngine(e.target.value)}
            >
              <MenuItem value="sqlite">{t("install", "dbSqlite")}</MenuItem>
              <MenuItem value="mysql">{t("install", "dbMysql")}</MenuItem>
            </TextField>
            {dbEngine === "mysql" && (
              <>
                <TextField label={t("install", "mysqlHost")} value={mysqlHost} onChange={(e) => setMysqlHost(e.target.value)} required />
                <TextField
                  label={t("install", "mysqlPort")}
                  type="number"
                  value={mysqlPort}
                  onChange={(e) => setMysqlPort(Number(e.target.value))}
                  required
                />
                <TextField label={t("install", "mysqlUser")} value={mysqlUser} onChange={(e) => setMysqlUser(e.target.value)} required />
                <TextField label={t("install", "mysqlDatabase")} value={mysqlDatabase} onChange={(e) => setMysqlDatabase(e.target.value)} required />
                <TextField
                  label={t("install", "mysqlPassword")}
                  type="password"
                  value={mysqlPassword}
                  onChange={(e) => setMysqlPassword(e.target.value)}
                />
              </>
            )}
            <TextField
              label={t("install", "storageRoot")}
              value={storageRoot}
              onChange={(e) => setStorageRoot(e.target.value)}
              helperText={t("install", "storageHint")}
              required
            />

            <Button type="submit" variant="contained" size="large" disabled={loading}>
              {loading ? t("install", "submitting") : t("install", "submit")}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
