import { FormEvent, useEffect, useState } from "react";
import { Alert, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import { changePassword, updateMyProfile } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";

export default function ProfilePage() {
  const { user, refreshMe, logout } = useAuth();
  const { t } = useLocale();
  const { roleLabel } = useLabels();
  const [name, setName] = useState(user?.name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPass, setSavingPass] = useState(false);

  useEffect(() => {
    if (user?.name) setName(user.name);
  }, [user?.name]);

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setSavingProfile(true);
    try {
      await updateMyProfile(name.trim());
      await refreshMe();
      setInfo(t("profile", "updated"));
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("profile", "profileError")
        )
      );
    } finally {
      setSavingProfile(false);
    }
  }

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (newPassword !== confirm) {
      setError(t("profile", "mismatch"));
      return;
    }
    if (!newPassword.trim()) {
      setError(t("profile", "required"));
      return;
    }
    setSavingPass(true);
    try {
      await changePassword(currentPassword, newPassword);
      setInfo(t("profile", "passwordUpdated"));
      setTimeout(() => logout(), 1200);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("profile", "passwordError")
        )
      );
    } finally {
      setSavingPass(false);
    }
  }

  return (
    <AppLayout>
      <PageShell
        title={t("profile", "title")}
        scrollBody={false}
        alerts={
          <>
            {error && <Alert severity="error">{error}</Alert>}
            {info && (
              <Alert severity="success" sx={{ mt: error ? 1 : 0 }}>
                {info}
              </Alert>
            )}
          </>
        }
      >
        <Stack spacing={3} maxWidth={520}>
          <Paper sx={{ p: 3 }} component="form" onSubmit={onSaveProfile}>
            <Typography variant="h6" gutterBottom>
              {t("profile", "personal")}
            </Typography>
            <Stack spacing={2}>
              <TextField
                label={t("profile", "name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("profile", "email")}
                value={user?.email || ""}
                fullWidth
                disabled
                helperText={t("profile", "emailHint")}
              />
              <TextField label={t("profile", "role")} value={roleLabel(user?.role)} fullWidth disabled />
              <Button type="submit" variant="contained" disabled={savingProfile || name.trim().length < 2}>
                {savingProfile ? t("common", "saving") : t("profile", "saveName")}
              </Button>
            </Stack>
          </Paper>

          <Paper sx={{ p: 3 }} component="form" onSubmit={onChangePassword}>
            <Typography variant="h6" gutterBottom>
              {t("profile", "changePassword")}
            </Typography>
            <Stack spacing={2}>
              <TextField
                label={t("profile", "current")}
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("profile", "newPassword")}
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("profile", "confirm")}
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                fullWidth
              />
              <Button type="submit" variant="contained" disabled={savingPass}>
                {savingPass ? t("common", "saving") : t("profile", "changePassword")}
              </Button>
            </Stack>
          </Paper>
        </Stack>
      </PageShell>
    </AppLayout>
  );
}
