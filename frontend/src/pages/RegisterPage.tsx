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

export default function RegisterPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("obrasociales");
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
            "No se pudo crear el usuario"
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
          <Typography variant="h4" gutterBottom>
            Crear usuario
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Completá tus datos. Te enviamos un enlace por correo para definir tu contraseña
            (válido 48 horas). Si el email ya existe, recibirás un enlace de recuperación.
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
              label="Tenant"
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              required
            />
            <TextField label="Nombre completo" value={name} onChange={(e) => setName(e.target.value)} required />
            <TextField
              label="Email laboral"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              helperText="Usá un buzón real: ahí llega el enlace de acceso"
            />
            <Button type="submit" variant="contained" size="large" disabled={loading || !!info}>
              {loading ? "Enviando…" : "Enviar enlace por email"}
            </Button>
            <Button component={RouterLink} to="/login" disabled={loading}>
              Volver al login
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
