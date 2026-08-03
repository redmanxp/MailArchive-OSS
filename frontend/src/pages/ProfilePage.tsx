import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import { changePassword, updateMyProfile } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { roleLabel } from "../utils/labels";

export default function ProfilePage() {
  const { user, refreshMe, logout } = useAuth();
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
      setInfo("Perfil actualizado");
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            "No se pudo actualizar el perfil"
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
      setError("Las contraseñas nuevas no coinciden");
      return;
    }
    if (!newPassword.trim()) {
      setError("La contraseña es obligatoria");
      return;
    }
    setSavingPass(true);
    try {
      await changePassword(currentPassword, newPassword);
      setInfo("Contraseña actualizada. Volvé a iniciar sesión.");
      setTimeout(() => logout(), 1200);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            "No se pudo cambiar la contraseña"
        )
      );
    } finally {
      setSavingPass(false);
    }
  }

  return (
    <AppLayout>
      <Typography variant="h4" gutterBottom>
        Mi perfil
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

      <Stack spacing={3} maxWidth={520}>
        <Paper sx={{ p: 3 }} component="form" onSubmit={onSaveProfile}>
          <Typography variant="h6" gutterBottom>
            Datos personales
          </Typography>
          <Stack spacing={2}>
            <TextField
              label="Nombre"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              fullWidth
            />
            <TextField label="Email" value={user?.email || ""} fullWidth disabled helperText="El email no se puede cambiar" />
            <TextField label="Rol" value={roleLabel(user?.role)} fullWidth disabled />
            <Button type="submit" variant="contained" disabled={savingProfile || name.trim().length < 2}>
              {savingProfile ? "Guardando…" : "Guardar nombre"}
            </Button>
          </Stack>
        </Paper>

        <Paper sx={{ p: 3 }} component="form" onSubmit={onChangePassword}>
          <Typography variant="h6" gutterBottom>
            Cambiar contraseña
          </Typography>
          <Stack spacing={2}>
            <TextField
              label="Contraseña actual"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              fullWidth
            />
            <TextField
              label="Nueva contraseña"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              fullWidth
            />
            <TextField
              label="Confirmar nueva"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              fullWidth
            />
            <Button type="submit" variant="contained" disabled={savingPass}>
              {savingPass ? "Guardando…" : "Cambiar contraseña"}
            </Button>
          </Stack>
        </Paper>
      </Stack>
    </AppLayout>
  );
}
