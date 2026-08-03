import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import { getSmtpSettings, testSmtpSettings, updateSmtpSettings, type SmtpSettings } from "../api/client";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SmtpSettings | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    getSmtpSettings()
      .then(setSettings)
      .catch((e) => setError(String(e?.response?.data?.detail || "Error")));
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setError(null);
    try {
      const saved = await updateSmtpSettings({
        ...settings,
        password: password || undefined,
      });
      setSettings(saved);
      setPassword("");
      setInfo("Configuración SMTP guardada.");
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  async function onTest() {
    if (!settings) return;
    setInfo(null);
    try {
      const r = await testSmtpSettings({ ...settings, password: password || undefined });
      setInfo(r.ok ? "Conexión SMTP OK" : `Falló: ${r.detail}`);
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  if (!settings) return <AppLayout><Typography>Cargando…</Typography></AppLayout>;

  return (
    <AppLayout>
      <Typography variant="h4" gutterBottom>
        Configuración
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        SMTP para enviar credenciales a usuarios nuevos (Mailcow).
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {info && <Alert severity={info.includes("Falló") ? "warning" : "success"} sx={{ mb: 2 }}>{info}</Alert>}

      <Paper sx={{ p: 3 }} component="form" onSubmit={onSave}>
        <Stack spacing={2}>
          <TextField
            label="Servidor SMTP"
            value={settings.host}
            onChange={(e) => setSettings({ ...settings, host: e.target.value })}
            placeholder="mail.newlicisalud.com.ar"
          />
          <TextField
            label="Puerto"
            type="number"
            value={settings.port}
            onChange={(e) => setSettings({ ...settings, port: Number(e.target.value) })}
          />
          <TextField
            label="Usuario (email completo)"
            value={settings.user}
            onChange={(e) => setSettings({ ...settings, user: e.target.value })}
          />
          <TextField
            label="Contraseña SMTP"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            helperText="Dejar vacío para no cambiar la guardada."
          />
          <TextField
            label="Remitente (From)"
            value={settings.from_email}
            onChange={(e) => setSettings({ ...settings, from_email: e.target.value })}
          />
          <TextField
            label="Nombre remitente"
            value={settings.from_name}
            onChange={(e) => setSettings({ ...settings, from_name: e.target.value })}
          />
          <FormControlLabel
            control={<Switch checked={settings.starttls} onChange={(e) => setSettings({ ...settings, starttls: e.target.checked })} />}
            label="STARTTLS (puerto 587)"
          />
          <FormControlLabel
            control={<Switch checked={settings.enabled} onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })} />}
            label="SMTP habilitado"
          />
          <Stack direction="row" spacing={2}>
            <Button type="button" variant="outlined" onClick={onTest}>
              Probar conexión
            </Button>
            <Button type="submit" variant="contained">
              Guardar
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </AppLayout>
  );
}
