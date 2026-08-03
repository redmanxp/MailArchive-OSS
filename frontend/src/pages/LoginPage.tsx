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
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantSlug, setTenantSlug] = useState("obrasociales");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await login(email, password, tenantSlug);
      navigate(user.must_change_password ? "/change-password" : "/app");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Login fallido";
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        position: "relative",
        display: "grid",
        placeItems: "center",
        background:
          "linear-gradient(160deg, #0B3D5C 0%, #1a5a7a 40%, #f3f6f8 40%, #f3f6f8 100%)",
        px: 2,
        py: 4,
      }}
    >
      <Button
        component={RouterLink}
        to="/register"
        variant="contained"
        color="secondary"
        sx={{
          position: "absolute",
          top: 16,
          right: 16,
          textTransform: "none",
          bgcolor: "rgba(255,255,255,0.95)",
          color: "primary.main",
          boxShadow: 1,
          "&:hover": { bgcolor: "#fff" },
        }}
      >
        Crear usuario
      </Button>
      <Container maxWidth="xs">
        <Paper elevation={0} sx={{ p: 4, border: "1px solid #d5dee5" }}>
          <Typography variant="h4" gutterBottom>
            MailArchive
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Iniciar sesión
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Stack component="form" spacing={2} onSubmit={onSubmit}>
            <TextField
              label="Tenant"
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              helperText="Organización (ej. obrasociales)"
            />
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
            <TextField
              label="Contraseña"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <Button type="submit" variant="contained" size="large" disabled={loading}>
              {loading ? "Ingresando…" : "Ingresar"}
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
