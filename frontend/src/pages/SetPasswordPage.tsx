import { FormEvent, useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Container,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { completePasswordLink, previewPasswordLink } from "../api/client";
import { useLocale } from "../i18n/LocaleContext";

export default function SetPasswordPage() {
  const { t } = useLocale();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [purpose, setPurpose] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) {
      setError(t("setPassword", "missingToken"));
      setLoading(false);
      return;
    }
    previewPasswordLink(token)
      .then((r) => {
        setName(r.name);
        setEmail(r.email);
        setPurpose(r.purpose);
      })
      .catch((err: unknown) => {
        setError(
          String(
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              t("setPassword", "invalidToken")
          )
        );
      })
      .finally(() => setLoading(false));
  }, [token, t]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== password2) {
      setError(t("setPassword", "mismatch"));
      return;
    }
    if (!password.trim()) {
      setError(t("setPassword", "required"));
      return;
    }
    setSaving(true);
    try {
      const r = await completePasswordLink(token, password);
      setInfo(r.message);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("setPassword", "failed")
        )
      );
    } finally {
      setSaving(false);
    }
  }

  const title = purpose === "reset" ? t("setPassword", "titleReset") : t("setPassword", "titleSet");

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
      <Container maxWidth="xs">
        <Paper elevation={0} sx={{ p: 4, border: "1px solid #d5dee5" }}>
          <Typography variant="h5" gutterBottom>
            {title}
          </Typography>
          {loading ? (
            <Box sx={{ display: "grid", placeItems: "center", py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {email && (
                <Typography color="text.secondary" sx={{ mb: 2 }}>
                  {name} — {email}
                </Typography>
              )}
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
              {!error || password ? (
                <Stack component="form" spacing={2} onSubmit={onSubmit}>
                  <TextField
                    label={t("setPassword", "newPassword")}
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={!!info}
                    helperText={t("setPassword", "minLength")}
                    inputProps={{ minLength: 8 }}
                  />
                  <TextField
                    label={t("setPassword", "confirmPassword")}
                    type="password"
                    value={password2}
                    onChange={(e) => setPassword2(e.target.value)}
                    required
                    disabled={!!info}
                  />
                  <Button type="submit" variant="contained" disabled={saving || !!info || !token}>
                    {saving ? t("setPassword", "submitting") : t("setPassword", "submit")}
                  </Button>
                </Stack>
              ) : null}
              <Button component={RouterLink} to="/login" sx={{ mt: 2 }}>
                {t("setPassword", "goLogin")}
              </Button>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  );
}
