import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
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
import ArchiveIcon from "@mui/icons-material/Archive";
import SearchIcon from "@mui/icons-material/Search";
import AppLayout from "../layouts/AppLayout";
import {
  archiveMessage,
  listAccountFolders,
  listAccountMessages,
  listAccounts,
  type AccountPublic,
  type FolderPublic,
  type ProviderMessage,
} from "../api/client";
import { formatDateTime } from "../utils/datetime";
import { folderDepth, folderLeafName } from "../utils/folders";
import { providerLabel } from "../utils/labels";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ArchivePage() {
  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [folders, setFolders] = useState<FolderPublic[]>([]);
  const [folderId, setFolderId] = useState("");
  const [messages, setMessages] = useState<ProviderMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<ProviderMessage | null>(null);
  const [deleteAfter, setDeleteAfter] = useState(false);

  useEffect(() => {
    listAccounts()
      .then((rows) => {
        setAccounts(rows);
        if (rows.length === 1) setAccountId(rows[0].id);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || "Error cargando cuentas")));
  }, []);

  useEffect(() => {
    if (!accountId) {
      setFolders([]);
      setFolderId("");
      setMessages([]);
      return;
    }
    setLoading(true);
    listAccountFolders(Number(accountId))
      .then((rows) => {
        setFolders(rows);
        const inbox =
          rows.find((f) => /inbox|bandeja/i.test(f.name)) ||
          rows.find((f) => f.path === "INBOX") ||
          rows[0];
        setFolderId(inbox?.id || "");
      })
      .catch((e) => setError(String(e?.response?.data?.detail || "Error cargando carpetas")))
      .finally(() => setLoading(false));
  }, [accountId]);

  async function loadMessages(e?: FormEvent) {
    e?.preventDefault();
    if (!accountId) return;
    setError(null);
    setLoading(true);
    try {
      const rows = await listAccountMessages(Number(accountId), {
        folder_id: folderId || undefined,
        limit: 50,
      });
      setMessages(rows);
      if (rows.length === 0) setInfo("No hay mensajes en esta carpeta.");
      else setInfo(null);
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    } finally {
      setLoading(false);
    }
  }

  async function confirmArchive() {
    if (!pending || !accountId) return;
    setLoading(true);
    setError(null);
    try {
      const folderMeta = folders.find((f) => f.id === folderId);
      const r = await archiveMessage({
        account_id: Number(accountId),
        message_id: pending.id,
        folder_id: folderId || pending.folder || undefined,
        folder_path: folderMeta?.path || folderMeta?.name || undefined,
        delete_after_archive: deleteAfter,
      });
      setInfo(
        deleteAfter
          ? `Archivado y borrado del proveedor: ${r.subject}`
          : `Archivado (queda en el proveedor): ${r.subject}`
      );
      setPending(null);
      setDeleteAfter(false);
      await loadMessages();
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al archivar"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      <Typography variant="h4" gutterBottom>
        Archivar
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Elegí cuenta y carpeta, listá mensajes y archivá. Si querés borrar del proveedor, hay que confirmarlo.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {info && <Alert severity="success" sx={{ mb: 2 }}>{info}</Alert>}

      <Paper sx={{ p: 3, mb: 3 }} component="form" onSubmit={loadMessages}>
        <Stack spacing={2} direction={{ xs: "column", md: "row" }}>
          <TextField
            select
            label="Cuenta"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
            fullWidth
            required
          >
            {accounts.map((a) => (
              <MenuItem key={a.id} value={a.id}>
                {a.email} ({providerLabel(a.provider)})
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Carpeta"
            value={folderId}
            onChange={(e) => setFolderId(e.target.value)}
            fullWidth
            disabled={!folders.length}
            SelectProps={{
              renderValue: (selected) => {
                const f = folders.find((x) => x.id === selected);
                if (!f) return "";
                const label = f.path || f.name;
                return `${folderLeafName(label, f.name)}${f.total_items != null ? ` (${f.total_items})` : ""}`;
              },
            }}
          >
            {folders.map((f) => {
              const label = f.path || f.name;
              const depth = folderDepth(label);
              return (
                <MenuItem key={f.id} value={f.id} sx={{ pl: 2 + depth * 2.5 }}>
                  {folderLeafName(label, f.name)}
                  {f.total_items != null ? ` (${f.total_items})` : ""}
                </MenuItem>
              );
            })}
          </TextField>
          <Tooltip title={loading ? "Cargando…" : "Listar"}>
            <span>
              <IconButton
                type="submit"
                color="primary"
                disabled={!accountId || loading}
                aria-label="Listar"
              >
                <SearchIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Asunto</TableCell>
              <TableCell>De</TableCell>
              <TableCell>Fecha</TableCell>
              <TableCell>Tamaño</TableCell>
              <TableCell>Adj.</TableCell>
              <TableCell align="right">Acción</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {messages.map((m) => (
              <TableRow key={m.id}>
                <TableCell>{m.subject || "(sin asunto)"}</TableCell>
                <TableCell>{m.from_address}</TableCell>
                <TableCell>{formatDateTime(m.received_at || m.sent_at)}</TableCell>
                <TableCell>{formatBytes(m.size_bytes)}</TableCell>
                <TableCell>{m.has_attachments ? "Sí" : "No"}</TableCell>
                <TableCell align="right">
                  <Tooltip title="Archivar">
                    <IconButton
                      size="small"
                      color="primary"
                      aria-label="Archivar"
                      onClick={() => { setPending(m); setDeleteAfter(false); }}
                    >
                      <ArchiveIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {messages.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography color="text.secondary">Sin mensajes cargados.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      <Dialog open={!!pending} onClose={() => setPending(null)}>
        <DialogTitle>Confirmar archivado</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Se guardará una copia local de: <strong>{pending?.subject || "(sin asunto)"}</strong>
          </DialogContentText>
          <FormControlLabel
            control={
              <Checkbox
                checked={deleteAfter}
                onChange={(e) => setDeleteAfter(e.target.checked)}
                color="warning"
              />
            }
            label="También borrar el correo del proveedor (Microsoft/IMAP)"
          />
          {deleteAfter && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Esta acción elimina el mensaje del buzón original. No se puede deshacer desde el proveedor.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPending(null)}>Cancelar</Button>
          <Button variant="contained" color={deleteAfter ? "warning" : "primary"} onClick={confirmArchive} disabled={loading}>
            {deleteAfter ? "Archivar y borrar" : "Archivar (conservar en proveedor)"}
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
}
