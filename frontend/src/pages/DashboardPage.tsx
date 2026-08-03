import { Alert, Button, Paper, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import { useAuth } from "../auth/AuthContext";
import { roleLabel } from "../utils/labels";

export default function DashboardPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <AppLayout>
      <Typography variant="h4" gutterBottom>
        Panel
      </Typography>
      <Stack spacing={2}>
        <Paper sx={{ p: 3 }} elevation={0}>
          <Typography variant="h6">Sesión</Typography>
          <Typography>Email: {user?.email}</Typography>
          <Typography>Rol: {roleLabel(user?.role)}</Typography>
        </Paper>

        <Paper sx={{ p: 3 }} elevation={0}>
          <Typography variant="h6" gutterBottom>
            Correo
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <Button component={RouterLink} to="/app/archive" variant="contained">
              Archivar mensajes
            </Button>
            <Button component={RouterLink} to="/app/bulk" variant="outlined">
              Archivado masivo
            </Button>
            <Button component={RouterLink} to="/app/mails" variant="outlined">
              Ver archivados
            </Button>
            <Button component={RouterLink} to="/app/accounts" variant="outlined">
              Cuentas
            </Button>
          </Stack>
        </Paper>

        {isAdmin && (
          <Paper sx={{ p: 3 }} elevation={0}>
            <Typography variant="h6" gutterBottom>
              Administración
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <Button component={RouterLink} to="/app/users" variant="contained">
                Gestionar usuarios
              </Button>
              <Button component={RouterLink} to="/app/settings" variant="outlined">
                Configuración SMTP
              </Button>
              <Button component={RouterLink} to="/app/audit" variant="outlined">
                Auditoría
              </Button>
            </Stack>
          </Paper>
        )}

        {!isAdmin && (
          <Alert severity="info">
            Bienvenido. Usá el menú lateral para vincular cuentas y archivar correos.
          </Alert>
        )}
      </Stack>
    </AppLayout>
  );
}
