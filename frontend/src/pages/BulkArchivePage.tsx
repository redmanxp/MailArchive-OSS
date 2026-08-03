import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  LinearProgress,
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
import RefreshIcon from "@mui/icons-material/Refresh";
import StopIcon from "@mui/icons-material/Stop";
import AppLayout from "../layouts/AppLayout";
import BulkPreparingModal from "../components/BulkPreparingModal";
import {
  cancelArchiveJob,
  getArchiveJob,
  listAccountFolders,
  listAccounts,
  listArchiveJobs,
  simulateBulkArchive,
  type AccountPublic,
  type ArchiveJob,
  type FolderPublic,
} from "../api/client";
import { formatDateTime } from "../utils/datetime";
import { folderDepth, folderLeafName } from "../utils/folders";
import { jobStatusLabel } from "../utils/labels";
import { saveBulkPreview } from "./BulkPreviewPage";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function BulkArchivePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [folders, setFolders] = useState<FolderPublic[]>([]);
  const [folderId, setFolderId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [olderDays, setOlderDays] = useState("");
  const [minSizeMb, setMinSizeMb] = useState("");
  const [onlyAttachments, setOnlyAttachments] = useState(false);
  const [limit, setLimit] = useState("200");
  const [deleteAfter, setDeleteAfter] = useState(false);
  const [jobs, setJobs] = useState<ArchiveJob[]>([]);
  const [showJobHistory, setShowJobHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancellingPrep, setCancellingPrep] = useState(false);
  const prepAbortRef = useRef<AbortController | null>(null);

  const limitNum = Math.min(2000, Math.max(1, Number(limit) || 200));
  const visibleJobs = showJobHistory
    ? jobs
    : jobs.filter((j) => j.status === "pending" || j.status === "running");

  useEffect(() => {
    listAccounts()
      .then((rows) => {
        setAccounts(rows);
        if (rows.length === 1) setAccountId(rows[0].id);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || "Error cuentas")));
    refreshJobs().catch(() => undefined);
  }, []);

  useEffect(() => {
    const started = (location.state as { startedJobId?: number } | null)?.startedJobId;
    if (started) {
      setInfo(`Job #${started} iniciado. Podés seguir el avance abajo.`);
      navigate("/app/bulk", { replace: true, state: {} });
      refreshJobs().catch(() => undefined);
    }
  }, [location.state, navigate]);

  useEffect(() => {
    if (!accountId) {
      setFolders([]);
      setFolderId("");
      return;
    }
    listAccountFolders(Number(accountId))
      .then((rows) => {
        setFolders(rows);
        const inbox = rows.find((f) => /inbox|bandeja/i.test(f.name)) || rows[0];
        setFolderId(inbox?.id || "");
      })
      .catch((e) => setError(String(e?.response?.data?.detail || "Error carpetas")));
  }, [accountId]);

  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === "pending" || j.status === "running");
    if (!hasRunning) return;
    const t = setInterval(() => {
      refreshJobs().catch(() => undefined);
    }, 2500);
    return () => clearInterval(t);
  }, [jobs]);

  function criteria() {
    const folderMeta = folders.find((f) => f.id === folderId);
    return {
      folder_id: folderId || undefined,
      folder_path: folderMeta?.path || folderMeta?.name,
      date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
      date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      older_than_days: olderDays ? Number(olderDays) : undefined,
      min_size_bytes: minSizeMb ? Math.round(Number(minSizeMb) * 1024 * 1024) : undefined,
      only_with_attachments: onlyAttachments || undefined,
    };
  }

  async function refreshJobs() {
    setJobs(await listArchiveJobs());
  }

  async function onSimulate(e?: FormEvent) {
    e?.preventDefault();
    if (!accountId) return;
    prepAbortRef.current?.abort();
    const ac = new AbortController();
    prepAbortRef.current = ac;
    setLoading(true);
    setCancellingPrep(false);
    setError(null);
    try {
      const r = await simulateBulkArchive(
        {
          account_id: Number(accountId),
          criteria: criteria(),
          limit: limitNum,
        },
        { signal: ac.signal }
      );
      if (!r.message_count) {
        setInfo("Simulación: 0 mensajes con esos criterios.");
        return;
      }
      const account = accounts.find((a) => a.id === Number(accountId));
      saveBulkPreview({
        account_id: Number(accountId),
        account_email: account?.email,
        criteria: criteria(),
        limit: limitNum,
        delete_after_archive: deleteAfter,
        messages: r.messages || [],
        total_bytes: r.total_bytes,
      });
      navigate("/app/bulk/preview");
    } catch (err: unknown) {
      const aborted =
        ac.signal.aborted ||
        (err as { code?: string; name?: string })?.code === "ERR_CANCELED" ||
        (err as { name?: string })?.name === "CanceledError";
      if (aborted) {
        setInfo("Preparación cancelada.");
        return;
      }
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    } finally {
      if (prepAbortRef.current === ac) prepAbortRef.current = null;
      setLoading(false);
      setCancellingPrep(false);
    }
  }

  function onCancelPrep() {
    setCancellingPrep(true);
    prepAbortRef.current?.abort();
  }

  return (
    <AppLayout>
      <BulkPreparingModal
        open={loading}
        cancelling={cancellingPrep}
        onCancel={onCancelPrep}
      />
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h4">Archivado masivo</Typography>
          <Typography color="text.secondary">
            Criterios → simular → revisar listado → aplicar → progreso del job
          </Typography>
        </Box>
        <Tooltip title="Actualizar procesos">
          <IconButton onClick={() => refreshJobs()} color="primary">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {info && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setInfo(null)}>
          {info}
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }} component="form" onSubmit={onSimulate}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
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
                  {a.email}
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
                  return folderLeafName(f.path || f.name, f.name);
                },
              }}
            >
              {folders.map((f) => {
                const label = f.path || f.name;
                const depth = folderDepth(label);
                return (
                  <MenuItem key={f.id} value={f.id} sx={{ pl: 2 + depth * 2.5 }}>
                    {folderLeafName(label, f.name)}
                  </MenuItem>
                );
              })}
            </TextField>
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="Desde"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="Hasta"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="Más antiguos que (días)"
              type="number"
              value={olderDays}
              onChange={(e) => setOlderDays(e.target.value)}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
            <TextField
              label="Tamaño mín. (MB)"
              type="number"
              value={minSizeMb}
              onChange={(e) => setMinSizeMb(e.target.value)}
              fullWidth
            />
            <TextField
              label="Límite"
              type="text"
              inputMode="numeric"
              value={limit}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "");
                setLimit(v);
              }}
              onBlur={() => {
                if (!limit || Number(limit) < 1) setLimit("200");
                else if (Number(limit) > 2000) setLimit("2000");
              }}
              helperText="1–2000"
              fullWidth
            />
            <FormControlLabel
              control={
                <Checkbox checked={onlyAttachments} onChange={(e) => setOnlyAttachments(e.target.checked)} />
              }
              label="Solo con adjuntos"
            />
          </Stack>
          <FormControlLabel
            control={
              <Checkbox
                checked={deleteAfter}
                onChange={(e) => setDeleteAfter(e.target.checked)}
                color="warning"
              />
            }
            label="Borrar del proveedor después de archivar (se confirma al aplicar)"
          />
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Iniciar proceso de archivado">
              <span>
                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  disabled={!accountId || loading}
                  sx={{ px: 3, py: 1.25, fontSize: "1rem", fontWeight: 600 }}
                >
                  {loading ? "Preparando…" : "Comenzar"}
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography variant="h6">Procesos en curso</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 1, flex: 1, textAlign: "right" }}>
            El archivado corre en segundo plano
          </Typography>          <FormControlLabel
            control={
              <Checkbox
                size="small"
                checked={showJobHistory}
                onChange={(e) => setShowJobHistory(e.target.checked)}
              />
            }
            label={<Typography variant="body2">Ver historial</Typography>}
          />
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell>Progreso</TableCell>
              <TableCell>Archivados</TableCell>
              <TableCell>Creado</TableCell>
              <TableCell align="right">Acciones</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleJobs.map((j) => (
              <TableRow key={j.id}>
                <TableCell>#{j.id}</TableCell>
                <TableCell>{jobStatusLabel(j.status)}</TableCell>
                <TableCell sx={{ minWidth: 160 }}>
                  <Typography variant="caption">
                    {j.processed_messages}/{j.total_messages} ({j.progress_pct}%)
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, j.progress_pct)}
                    sx={{ mt: 0.5 }}
                    color={j.status === "failed" ? "error" : j.status === "completed" ? "success" : "primary"}
                  />
                </TableCell>
                <TableCell>
                  {j.archived_messages} ok · {j.skipped_messages} skip · {j.failed_messages} err
                  <Typography variant="caption" display="block">
                    {formatBytes(j.archived_bytes)} / {formatBytes(j.total_bytes)}
                  </Typography>
                </TableCell>
                <TableCell>{formatDateTime(j.created_at)}</TableCell>
                <TableCell align="right">
                  <Tooltip title="Actualizar">
                    <IconButton
                      size="small"
                      onClick={async () => {
                        const fresh = await getArchiveJob(j.id);
                        setJobs((prev) => prev.map((x) => (x.id === j.id ? fresh : x)));
                      }}
                    >
                      <RefreshIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  {(j.status === "pending" || j.status === "running") && (
                    <Tooltip title="Cancelar">
                      <IconButton
                        size="small"
                        color="warning"
                        onClick={async () => {
                          await cancelArchiveJob(j.id);
                          await refreshJobs();
                        }}
                      >
                        <StopIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {visibleJobs.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography color="text.secondary">
                    {showJobHistory ? "Sin procesos." : "No hay procesos en curso."}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </AppLayout>
  );
}
