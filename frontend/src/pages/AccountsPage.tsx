import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import LinkOffIcon from "@mui/icons-material/LinkOff";
import AppLayout from "../layouts/AppLayout";
import ConfirmDialog from "../components/ConfirmDialog";
import { useAuth } from "../auth/AuthContext";
import {
  createImapAccount,
  deleteAccount,
  listAccounts,
  startMicrosoftOAuth,
  testImapConnection,
  type AccountPublic,
} from "../api/client";
import { accountStatusLabel, providerLabel } from "../utils/labels";

type LinkStep = "provider" | "imap";
type ProviderChoice = "microsoft365" | "imap" | "";

export default function AccountsPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isStaff = user?.role === "admin" || user?.role === "supervisor";

  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [unlinkId, setUnlinkId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const [linkOpen, setLinkOpen] = useState(false);
  const [linkStep, setLinkStep] = useState<LinkStep>("provider");
  const [provider, setProvider] = useState<ProviderChoice>("");

  const [host, setHost] = useState("mail.newlicisalud.com.ar");
  const [port, setPort] = useState(993);
  const [ssl, setSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    const linked = params.get("linked");
    const email = params.get("email");
    const oauthError = params.get("error");
    if (linked === "1") {
      setInfo(`Cuenta Microsoft vinculada: ${email || ""}`);
      navigate("/app/accounts", { replace: true });
    } else if (oauthError) {
      setError(`Error OAuth: ${oauthError}`);
      navigate("/app/accounts", { replace: true });
    }
  }, [params, navigate]);

  async function refresh() {
    setAccounts(await listAccounts());
  }

  useEffect(() => {
    refresh().catch((err) => {
      setError(err?.response?.data?.detail || "No se pudieron cargar las cuentas");
    });
  }, []);

  function openLinkModal() {
    setProvider("");
    setLinkStep("provider");
    setPassword("");
    setError(null);
    setLinkOpen(true);
  }

  function closeLinkModal() {
    if (loading) return;
    setLinkOpen(false);
    setLinkStep("provider");
    setProvider("");
  }

  async function onContinueProvider() {
    if (provider === "microsoft365") {
      setLoading(true);
      setError(null);
      try {
        const { authorize_url } = await startMicrosoftOAuth();
        window.location.href = authorize_url;
      } catch (err: unknown) {
        setError(
          String(
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              "Error OAuth"
          )
        );
        setLoading(false);
      }
      return;
    }
    if (provider === "imap") {
      setLinkStep("imap");
    }
  }

  async function onTestImap() {
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const res = await testImapConnection({ host, port, ssl, username, password });
      setInfo(res.ok ? `IMAP OK (${res.email || username})` : `Falló: ${res.detail}`);
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error")
      );
    } finally {
      setLoading(false);
    }
  }

  async function onSaveImap(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await createImapAccount({ host, port, ssl, username, password });
      setInfo("Cuenta IMAP guardada");
      setPassword("");
      setLinkOpen(false);
      setLinkStep("provider");
      await refresh();
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error")
      );
    } finally {
      setLoading(false);
    }
  }

  async function confirmUnlink() {
    if (unlinkId == null) return;
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await deleteAccount(unlinkId);
      setInfo("Cuenta desvinculada correctamente.");
      setUnlinkId(null);
      await refresh();
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            "No se pudo desvincular"
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const title = isStaff ? "Cuentas de correo" : "Mis cuentas de correo";

  return (
    <AppLayout>
      {info && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setInfo(null)}>
          {info}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h4">{title}</Typography>
          <Typography color="text.secondary" variant="body2">
            {isStaff
              ? "Cada usuario vincula sus propias cuentas. Como admin/supervisor ves todas las del tenant."
              : "Podés vincular más de una cuenta (Microsoft 365 o IMAP)."}
          </Typography>
        </Box>
        <Tooltip title="Vincular otra cuenta">
          <IconButton color="primary" onClick={openLinkModal} aria-label="Vincular cuenta" size="large">
            <AddIcon />
          </IconButton>
        </Tooltip>
      </Stack>

      <Paper sx={{ p: 0 }} elevation={0}>
        {accounts.length === 0 ? (
          <Box sx={{ p: 3 }}>
            <Typography color="text.secondary">
              No hay cuentas vinculadas. Usá el botón + para agregar una.
            </Typography>
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Proveedor</TableCell>
                <TableCell>Email</TableCell>
                {isStaff && <TableCell>Usuario</TableCell>}
                <TableCell>Estado</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {accounts.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell>{providerLabel(a.provider)}</TableCell>
                  <TableCell>
                    {a.email}
                    {a.is_mine === false ? (
                      <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                        (ajena)
                      </Typography>
                    ) : null}
                  </TableCell>
                  {isStaff && (
                    <TableCell>
                      {a.owner_name || a.owner_email || `user #${a.user_id}`}
                      {a.owner_email && a.owner_name ? (
                        <Typography variant="caption" display="block" color="text.secondary">
                          {a.owner_email}
                        </Typography>
                      ) : null}
                    </TableCell>
                  )}
                  <TableCell>
                    {accountStatusLabel(a.status)}
                    {a.last_error ? (
                      <Typography variant="caption" display="block" color="error">
                        {a.last_error}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell align="right">
                    {(a.is_mine !== false || isStaff) && (
                      <Tooltip title="Desvincular">
                        <IconButton
                          color="error"
                          onClick={() => setUnlinkId(a.id)}
                          aria-label="Desvincular"
                          size="small"
                        >
                          <LinkOffIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      <Dialog open={linkOpen} onClose={closeLinkModal} fullWidth maxWidth="sm">
        <DialogTitle>
          {linkStep === "provider" ? "Vincular cuenta" : "Cuenta IMAP"}
        </DialogTitle>
        <DialogContent>
          {linkStep === "provider" && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Typography color="text.secondary" variant="body2">
                Elegí el proveedor. La cuenta queda vinculada a tu usuario ({user?.email}).
                Aunque el mismo buzón ya esté vinculado a otro usuario, debés completar el
                login/credenciales vos (no se reutilizan tokens ajenos).
              </Typography>
              <TextField
                select
                label="Proveedor"
                value={provider}
                onChange={(e) => setProvider(e.target.value as ProviderChoice)}
                fullWidth
              >
                <MenuItem value="microsoft365">Microsoft 365</MenuItem>
                <MenuItem value="imap">IMAP</MenuItem>
              </TextField>
            </Stack>
          )}
          {linkStep === "imap" && (
            <Stack spacing={2} component="form" id="imap-link-form" onSubmit={onSaveImap} sx={{ pt: 1 }}>
              <TextField label="Servidor" value={host} onChange={(e) => setHost(e.target.value)} required fullWidth />
              <TextField
                label="Puerto"
                type="number"
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
                required
                fullWidth
              />
              <FormControlLabel
                control={<Switch checked={ssl} onChange={(e) => setSsl(e.target.checked)} />}
                label="SSL"
              />
              <TextField
                label="Usuario"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label="Contraseña"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                fullWidth
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {linkStep === "imap" && (
            <>
              <Button onClick={() => setLinkStep("provider")} disabled={loading}>
                Atrás
              </Button>
              <Button onClick={onTestImap} disabled={loading}>
                Probar
              </Button>
              <Button type="submit" form="imap-link-form" variant="contained" disabled={loading}>
                Guardar
              </Button>
            </>
          )}
          {linkStep === "provider" && (
            <>
              <Button onClick={closeLinkModal} disabled={loading}>
                Cancelar
              </Button>
              <Button
                variant="contained"
                onClick={onContinueProvider}
                disabled={loading || !provider}
              >
                Continuar
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={unlinkId != null}
        title="Desvincular cuenta"
        message="¿Desvincular esta cuenta? Se borrarán los tokens guardados."
        confirmLabel="Desvincular"
        confirmColor="error"
        loading={loading}
        onCancel={() => !loading && setUnlinkId(null)}
        onConfirm={confirmUnlink}
      />
    </AppLayout>
  );
}
