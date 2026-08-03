import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Pagination,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import VisibilityIcon from "@mui/icons-material/Visibility";
import AppLayout from "../layouts/AppLayout";
import ConfirmDialog from "../components/ConfirmDialog";
import BulkPreparingModal from "../components/BulkPreparingModal";
import MailBodyViewer from "../components/MailBodyViewer";
import {
  previewProviderMessage,
  downloadProviderAttachmentToDisk,
  startBulkArchive,
  type ProviderMessage,
  type ProviderMessageDetail,
} from "../api/client";
import { formatDateTime } from "../utils/datetime";

const STORAGE_KEY = "ma_bulk_preview";
const PAGE_SIZE = 25;

export type BulkPreviewPayload = {
  account_id: number;
  account_email?: string;
  criteria: Record<string, unknown>;
  limit: number;
  delete_after_archive: boolean;
  messages: ProviderMessage[];
  total_bytes: number;
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function saveBulkPreview(payload: BulkPreviewPayload) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function loadBulkPreview(): BulkPreviewPayload | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as BulkPreviewPayload;
  } catch {
    return null;
  }
}

export default function BulkPreviewPage() {
  const navigate = useNavigate();
  const [payload, setPayload] = useState<BulkPreviewPayload | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [detail, setDetail] = useState<ProviderMessageDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const data = loadBulkPreview();
    if (!data || !data.messages?.length) {
      navigate("/app/bulk", { replace: true });
      return;
    }
    setPayload(data);
    setSelected(new Set(data.messages.map((m) => m.id)));
    setPage(1);
  }, [navigate]);

  const selectedMessages = useMemo(() => {
    if (!payload) return [];
    return payload.messages.filter((m) => selected.has(m.id));
  }, [payload, selected]);

  const selectedBytes = useMemo(
    () => selectedMessages.reduce((acc, m) => acc + (m.size_bytes || 0), 0),
    [selectedMessages]
  );

  const pageCount = Math.max(1, Math.ceil((payload?.messages.length || 0) / PAGE_SIZE));
  const pageRows = useMemo(() => {
    if (!payload) return [];
    const start = (page - 1) * PAGE_SIZE;
    return payload.messages.slice(start, start + PAGE_SIZE);
  }, [payload, page]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    if (!payload) return;
    setSelected(checked ? new Set(payload.messages.map((m) => m.id)) : new Set());
  }

  function togglePage(checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const m of pageRows) {
        if (checked) next.add(m.id);
        else next.delete(m.id);
      }
      return next;
    });
  }

  async function onView(m: ProviderMessage) {
    if (!payload) return;
    setDetailLoading(true);
    setError(null);
    try {
      const folderId = typeof payload.criteria.folder_id === "string" ? payload.criteria.folder_id : undefined;
      const d = await previewProviderMessage(payload.account_id, m.id, folderId);
      setDetail(d);
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "No se pudo abrir")
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function onApply() {
    if (!payload || selectedMessages.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const job = await startBulkArchive({
        account_id: payload.account_id,
        criteria: payload.criteria,
        delete_after_archive: payload.delete_after_archive,
        limit: selectedMessages.length,
        message_ids: selectedMessages.map((m) => m.id),
        total_bytes_hint: selectedBytes,
      });
      sessionStorage.removeItem(STORAGE_KEY);
      setConfirm(false);
      navigate("/app/bulk", { replace: true, state: { startedJobId: job.id } });
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al iniciar")
      );
    } finally {
      setLoading(false);
    }
  }

  if (!payload) {
    return (
      <AppLayout>
        <LinearProgress />
      </AppLayout>
    );
  }

  const allChecked = selected.size === payload.messages.length && payload.messages.length > 0;
  const pageAllChecked = pageRows.length > 0 && pageRows.every((m) => selected.has(m.id));
  const pageSomeChecked = pageRows.some((m) => selected.has(m.id)) && !pageAllChecked;

  return (
    <AppLayout>
      <BulkPreparingModal
        open={loading}
        title="Iniciando archivado"
        message="Creando el proceso. Después seguirá en segundo plano."
        showCancel={false}
      />
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          bgcolor: "background.default",
          pb: 1,
          mb: 1,
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <IconButton onClick={() => navigate("/app/bulk")} aria-label="Volver">
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h5">Revisión previa</Typography>
            <Typography color="text.secondary" variant="body2">
              Desmarcá lo que querés dejar en el servidor. Luego aplicá el archivado.
              {payload.account_email ? ` · ${payload.account_email}` : ""}
            </Typography>
          </Box>
          <Tooltip title="Iniciar proceso de archivado">
            <span>
              <Button
                variant="contained"
                color="success"
                size="large"
                startIcon={<PlayArrowIcon />}
                disabled={selected.size === 0 || loading}
                onClick={() => setConfirm(true)}
                sx={{ px: 3, py: 1.25, fontSize: "1rem", fontWeight: 600 }}
              >
                {loading ? "Iniciando…" : "Iniciar"}
              </Button>
            </span>
          </Tooltip>
        </Stack>

        {error && (
          <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Paper sx={{ p: 1.25 }} elevation={0} variant="outlined">
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
            <Typography variant="body2" sx={{ flex: 1 }}>
              Seleccionados: <strong>{selected.size}</strong> / {payload.messages.length} ·{" "}
              {formatBytes(selectedBytes)}
              {payload.delete_after_archive ? " · se borrarán del proveedor" : " · se conservan en el proveedor"}
            </Typography>
            <Button size="small" onClick={() => toggleAll(true)} disabled={allChecked}>
              Marcar todos
            </Button>
            <Button size="small" onClick={() => toggleAll(false)} disabled={selected.size === 0}>
              Desmarcar todos
            </Button>
          </Stack>
        </Paper>
      </Box>

      <Paper elevation={0} variant="outlined">
        <TableContainer sx={{ maxHeight: "calc(100vh - 260px)" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ bgcolor: "background.paper" }}>
                  <Checkbox
                    checked={pageAllChecked}
                    indeterminate={pageSomeChecked}
                    onChange={(e) => togglePage(e.target.checked)}
                  />
                </TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600 }}>Asunto</TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600 }}>De</TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600 }}>Fecha</TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600, width: 72 }} align="center">
                  Adj.
                </TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600 }}>Tamaño</TableCell>
                <TableCell sx={{ bgcolor: "background.paper", fontWeight: 600 }} align="right">
                  Ver
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {pageRows.map((m) => (
                <TableRow key={m.id} hover selected={selected.has(m.id)}>
                  <TableCell padding="checkbox">
                    <Checkbox checked={selected.has(m.id)} onChange={() => toggle(m.id)} />
                  </TableCell>
                  <TableCell>{m.subject || "(sin asunto)"}</TableCell>
                  <TableCell>{m.from_address}</TableCell>
                  <TableCell>{formatDateTime(m.received_at || m.sent_at)}</TableCell>
                  <TableCell align="center">{m.has_attachments ? "Sí" : "—"}</TableCell>
                  <TableCell>{formatBytes(m.size_bytes || 0)}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Ver correo">
                      <IconButton size="small" onClick={() => onView(m)} disabled={detailLoading}>
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        {payload.messages.length > PAGE_SIZE && (
          <Stack direction="row" justifyContent="center" sx={{ py: 1 }}>
            <Pagination size="small" count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
          </Stack>
        )}
      </Paper>

      <ConfirmDialog
        open={confirm}
        title="Aplicar archivado masivo"
        message={
          payload.delete_after_archive
            ? `Se archivarán ${selected.size} mensajes (${formatBytes(selectedBytes)}) y se BORRARÁN del proveedor. Los desmarcados quedan en el servidor. ¿Continuar?`
            : `Se archivarán ${selected.size} mensajes (${formatBytes(selectedBytes)}). Los desmarcados quedan en el servidor. ¿Continuar?`
        }
        confirmLabel="Aplicar"
        confirmColor={payload.delete_after_archive ? "warning" : "primary"}
        loading={loading}
        onCancel={() => !loading && setConfirm(false)}
        onConfirm={onApply}
      />

      <Dialog
        open={!!detail}
        onClose={() => setDetail(null)}
        fullWidth
        maxWidth="md"
        PaperProps={{ sx: { minHeight: "82vh" } }}
      >
        <DialogTitle sx={{ py: 1.5 }}>{detail?.subject || "(sin asunto)"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 1.5, pb: 2 }}>
          {detail && (
            <>
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                  gap: 1,
                  columnGap: 3,
                }}
              >
                <Box>
                  <Typography variant="body2">
                    <strong>De:</strong> {detail.from_address}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Para:</strong> {(detail.to_addresses || []).join(", ") || "—"}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    <strong>Fecha:</strong> {formatDateTime(detail.received_at || detail.sent_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Tamaño:</strong> {formatBytes(detail.size_bytes || 0)}
                    {(detail.attachments?.length || detail.has_attachments)
                      ? ` · ${detail.attachments?.length || "con"} adjunto(s)`
                      : ""}
                  </Typography>
                </Box>
              </Box>
              <MailBodyViewer
                text={detail.body_text}
                html={detail.body_html}
                isHtml={detail.body_is_html}
                minHeight={420}
                maxHeight="48vh"
              />
              {(detail.attachments?.length ?? 0) > 0 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Adjuntos
                  </Typography>
                  <Stack spacing={0.5}>
                    {detail.attachments!.map((a) => (
                      <Stack key={a.id} direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2">
                          {a.filename} ({formatBytes(a.size_bytes)})
                        </Typography>
                        <Tooltip title="Descargar adjunto">
                          <IconButton
                            size="small"
                            aria-label="Descargar adjunto"
                            onClick={async () => {
                              try {
                                const folderId =
                                  typeof payload.criteria.folder_id === "string"
                                    ? payload.criteria.folder_id
                                    : undefined;
                                await downloadProviderAttachmentToDisk(
                                  payload.account_id,
                                  detail.id,
                                  a.id,
                                  folderId
                                );
                              } catch (err: unknown) {
                                setError(
                                  String(
                                    (err as { response?: { data?: { detail?: string } } })?.response?.data
                                      ?.detail || "Error al descargar adjunto"
                                  )
                                );
                              }
                            }}
                          >
                            <DownloadIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    ))}
                  </Stack>
                </Box>
              )}
              <Button onClick={() => setDetail(null)} size="small" sx={{ alignSelf: "flex-start" }}>
                Cerrar
              </Button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
