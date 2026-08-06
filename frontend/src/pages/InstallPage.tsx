import { FormEvent, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Container,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { installApp } from "../api/client";
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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await installApp({
        tenant_name: tenantName,
        tenant_slug: tenantSlug,
        admin_name: adminName,
        admin_email: adminEmail,
        admin_password: adminPassword || undefined,
      });
      onInstalled();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        t("install", "failed");
      setError(String(msg));
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
      }}
    >
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: 4, border: "1px solid #d5dee5" }}>
          <Typography variant="h4" gutterBottom>
            {t("install", "title")}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            {t("install", "subtitle")}
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Stack component="form" spacing={2} onSubmit={onSubmit}>
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
            <Button type="submit" variant="contained" size="large" disabled={loading}>
              {loading ? t("install", "submitting") : t("install", "submit")}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
