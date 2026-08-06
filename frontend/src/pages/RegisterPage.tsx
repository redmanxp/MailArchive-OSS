import { FormEvent, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
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
import { selfRegister } from "../api/client";
import BrandLogo from "../components/BrandLogo";
import { useLocale } from "../i18n/LocaleContext";

export default function RegisterPage() {
  const { t } = useLocale();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      const r = await selfRegister({ name, email, tenant_slug: tenantSlug });
      setInfo(r.message);
      setTimeout(() => navigate("/login"), 3500);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("register", "failed")
        )
      );
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
          "linear-gradient(160deg, #0B3D5C 0%, #1a5a7a 40%, #f3f6f8 40%, #f3f6f8 100%)",
        px: 2,
        py: 4,
      }}
    >
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: 4, border: "1px solid #d5dee5" }}>
          <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
            <BrandLogo kind="full" height={120} maxWidth={240} />
          </Box>
          <Typography color="text.secondary" sx={{ mb: 3, textAlign: "center" }}>
            {t("register", "subtitle")}
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          {info && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {info}
            </Alert>
          )}
          <Stack component="form" spacing={2} onSubmit={onSubmit}>
            <TextField
              label={t("register", "tenant")}
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              required
            />
            <TextField
              label={t("register", "name")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <TextField
              label={t("register", "email")}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              helperText={t("register", "emailHint")}
            />
            <Button type="submit" variant="contained" size="large" disabled={loading || !!info}>
              {loading ? t("register", "submitting") : t("register", "submit")}
            </Button>
            <Button component={RouterLink} to="/login" disabled={loading}>
              {t("register", "backLogin")}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
