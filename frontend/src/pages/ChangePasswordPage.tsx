import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import { useAuth } from "../auth/AuthContext";
import { useLocale } from "../i18n/LocaleContext";

export default function ChangePasswordPage() {
  const { changePassword, user } = useAuth();
  const { t } = useLocale();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError(t("changePassword", "mismatch"));
      return;
    }
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setOk(t("changePassword", "success"));
      setTimeout(() => navigate("/login"), 1200);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        t("changePassword", "failed");
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", px: 2 }}>
      <Container maxWidth="xs">
        <Paper sx={{ p: 4, border: "1px solid #d5dee5" }} elevation={0}>
          <Typography variant="h5" gutterBottom>
            {t("changePassword", "title")}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {user?.email || t("changePassword", "user")} — {t("changePassword", "subtitle")}
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          {ok && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {ok}
            </Alert>
          )}
          <Stack component="form" spacing={2} onSubmit={onSubmit}>
            <TextField
              label={t("changePassword", "current")}
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <TextField
              label={t("changePassword", "newPassword")}
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <TextField
              label={t("changePassword", "confirm")}
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
            <Button type="submit" variant="contained" disabled={loading}>
              {loading ? t("changePassword", "submitting") : t("changePassword", "submit")}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
