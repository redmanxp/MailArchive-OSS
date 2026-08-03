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

export default function SetPasswordPage() {
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
      setError("Enlace inválido: falta el token");
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
              "El enlace no es válido o expiró"
          )
        );
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== password2) {
      setError("Las contraseñas no coinciden");
      return;
    }
    if (!password.trim()) {
      setError("La contraseña es obligatoria");
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
            "No se pudo guardar la contraseña"
        )
      );
    } finally {
      setSaving(false);
    }
  }

  const title = purpose === "reset" ? "Restablecer contraseña" : "Definir contraseña";

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
                    label="Nueva contraseña"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={!!info}
                  />
                  <TextField
                    label="Repetir contraseña"
                    type="password"
                    value={password2}
                    onChange={(e) => setPassword2(e.target.value)}
                    required
                    disabled={!!info}
                  />
                  <Button type="submit" variant="contained" disabled={saving || !!info || !token}>
                    {saving ? "Guardando…" : "Guardar contraseña"}
                  </Button>
                </Stack>
              ) : null}
              <Button component={RouterLink} to="/login" sx={{ mt: 2 }}>
                Ir al login
              </Button>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  );
}
