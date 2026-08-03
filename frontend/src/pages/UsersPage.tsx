import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import LockResetIcon from "@mui/icons-material/LockReset";
import PersonOffIcon from "@mui/icons-material/PersonOff";
import AppLayout from "../layouts/AppLayout";
import ConfirmDialog from "../components/ConfirmDialog";
import {
  createUser,
  deactivateUser,
  listUsers,
  resetUserPassword,
  updateUser,
  type UserAdmin,
} from "../api/client";
import { roleLabel, userStatusLabel } from "../utils/labels";

const ROLES = [
  { value: "admin", label: "Administrador" },
  { value: "supervisor", label: "Supervisor" },
  { value: "user", label: "Usuario" },
  { value: "readonly", label: "Solo lectura" },
];

const STATUSES = [
  { value: "active", label: "Activo" },
  { value: "inactive", label: "Inactivo" },
];

export default function UsersPage() {
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [sendEmail, setSendEmail] = useState(true);
  const [resetTarget, setResetTarget] = useState<UserAdmin | null>(null);
  const [editOpen, setEditOpen] = useState<UserAdmin | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("user");
  const [editStatus, setEditStatus] = useState("active");
  const [saving, setSaving] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<UserAdmin | null>(null);

  async function refresh() {
    setUsers(await listUsers());
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e?.response?.data?.detail || "Error cargando usuarios")));
  }, []);

  function openEdit(u: UserAdmin) {
    setEditOpen(u);
    setEditName(u.name);
    setEditRole(u.role);
    setEditStatus(u.status);
    setError(null);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    try {
      const r = await createUser({ name, email, role, send_welcome_email: sendEmail });
      setInfo(
        r.email_sent
          ? `Usuario ${r.email} creado. Se envió enlace para definir contraseña.`
          : `Usuario ${r.email} creado. Email no enviado: ${r.email_detail || "SMTP no configurado"}`
      );
      setName("");
      setEmail("");
      setRole("user");
      await refresh();
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  async function onSaveEdit() {
    if (!editOpen) return;
    setSaving(true);
    setError(null);
    try {
      await updateUser(editOpen.id, {
        name: editName.trim(),
        role: editRole,
        status: editStatus,
      });
      setInfo(`Usuario ${editOpen.email} actualizado`);
      setEditOpen(null);
      await refresh();
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al editar"));
    } finally {
      setSaving(false);
    }
  }

  async function onSendReset() {
    if (!resetTarget) return;
    try {
      const r = await resetUserPassword(resetTarget.id, true);
      setInfo(
        r.email_sent
          ? `Se envió enlace de restablecimiento a ${resetTarget.email}`
          : `No se pudo enviar email: ${r.email_detail}`
      );
      setResetTarget(null);
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  return (
    <AppLayout>
      <Typography variant="h4" gutterBottom>
        Usuarios
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {info && <Alert severity="success" sx={{ mb: 2 }}>{info}</Alert>}

      <Stack spacing={3}>
        <Paper sx={{ p: 3 }} component="form" onSubmit={onCreate}>
          <Typography variant="h6" gutterBottom>
            Crear usuario
          </Typography>
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField label="Nombre" value={name} onChange={(e) => setName(e.target.value)} required fullWidth />
              <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required fullWidth />
            </Stack>
            <TextField select label="Rol" value={role} onChange={(e) => setRole(e.target.value)} fullWidth>
              {ROLES.map((r) => (
                <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={2} alignItems="center">
              <Button type="submit" variant="contained">
                Crear y enviar enlace
              </Button>
              <Chip
                label={sendEmail ? "Email: sí" : "Email: no"}
                onClick={() => setSendEmail(!sendEmail)}
                color={sendEmail ? "primary" : "default"}
                variant={sendEmail ? "filled" : "outlined"}
              />
            </Stack>
          </Stack>
        </Paper>

        <Paper sx={{ p: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Nombre</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Rol</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.id}</TableCell>
                  <TableCell>{u.name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{roleLabel(u.role)}</TableCell>
                  <TableCell>{userStatusLabel(u.status)}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Editar">
                      <IconButton size="small" onClick={() => openEdit(u)} aria-label="Editar">
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Enviar enlace de restablecimiento">
                      <IconButton size="small" onClick={() => setResetTarget(u)} aria-label="Restablecer pass">
                        <LockResetIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Eliminar">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => setDeactivateTarget(u)}
                        aria-label="Eliminar"
                      >
                        <PersonOffIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      </Stack>

      <Dialog open={!!editOpen} onClose={() => setEditOpen(null)} fullWidth maxWidth="sm">
        <DialogTitle>Editar usuario — {editOpen?.email}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              fullWidth
              required
            />
            <TextField select label="Rol" value={editRole} onChange={(e) => setEditRole(e.target.value)} fullWidth>
              {ROLES.map((r) => (
                <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Estado"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              fullWidth
            >
              {STATUSES.map((s) => (
                <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(null)}>Cancelar</Button>
          <Button variant="contained" onClick={onSaveEdit} disabled={saving || !editName.trim()}>
            {saving ? "Guardando…" : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={!!resetTarget}
        title="Restablecer contraseña"
        message={`¿Enviar a ${resetTarget?.email} un enlace para definir una nueva contraseña?`}
        confirmLabel="Enviar enlace"
        onCancel={() => setResetTarget(null)}
        onConfirm={onSendReset}
      />

      <ConfirmDialog
        open={!!deactivateTarget}
        title="Desactivar usuario"
        message={`¿Desactivar a ${deactivateTarget?.email}? No podrá iniciar sesión.`}
        confirmLabel="Desactivar"
        confirmColor="error"
        onCancel={() => setDeactivateTarget(null)}
        onConfirm={async () => {
          if (!deactivateTarget) return;
          try {
            await deactivateUser(deactivateTarget.id);
            setDeactivateTarget(null);
            setInfo(`Usuario ${deactivateTarget.email} desactivado`);
            await refresh();
          } catch (err: unknown) {
            setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
          }
        }}
      />
    </AppLayout>
  );
}
