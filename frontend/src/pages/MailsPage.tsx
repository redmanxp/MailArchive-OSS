import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DownloadIcon from "@mui/icons-material/Download";
import RestoreIcon from "@mui/icons-material/Restore";
import VisibilityIcon from "@mui/icons-material/Visibility";
import AppLayout from "../layouts/AppLayout";
import ConfirmDialog from "../components/ConfirmDialog";
import MailBodyViewer from "../components/MailBodyViewer";
import { useAuth } from "../auth/AuthContext";
import {
  bulkDownloadArchivedMailsToDisk,
  bulkRestoreArchivedMails,
  downloadAttachmentToDisk,
  downloadEmlToDisk,
  getArchivedMail,
  listAccounts,
  restoreArchivedMail,
  searchMailIds,
  searchMails,
  type AccountPublic,
  type ArchivedMail,
  type ArchivedMailDetail,
} from "../api/client";
import { formatDateTime, formatDateTimeShort } from "../utils/datetime";

const PAGE_SIZE = 25;

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const fieldSx = {
  "& .MuiInputBase-input": { py: 0.75, fontSize: "0.8125rem" },
  "& .MuiInputLabel-root": { fontSize: "0.8125rem" },
};

export default function MailsPage() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [onlyAttachments, setOnlyAttachments] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [mails, setMails] = useState<ArchivedMail[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<ArchivedMailDetail | null>(null);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [bulkRestoreOpen, setBulkRestoreOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const canRestore = user?.role !== "readonly";
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const pageAllChecked = mails.length > 0 && mails.every((m) => selected.has(m.id));
  const pageSomeChecked = mails.some((m) => selected.has(m.id)) && !pageAllChecked;

  const filterParams = useMemo(
    () => ({
      q: q.trim() || undefined,
      account_id: accountId === "" ? undefined : Number(accountId),
      from_address: fromAddress.trim() || undefined,
      has_attachments: onlyAttachments ? true : undefined,
      date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
      date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
    }),
    [q, accountId, fromAddress, onlyAttachments, dateFrom, dateTo]
  );

  useEffect(() => {
    listAccounts().then(setAccounts).catch(() => undefined);
  }, []);

  async function load(nextPage = page) {
    setLoading(true);
    setError(null);
    try {
      const r = await searchMails({
        ...filterParams,
        limit: PAGE_SIZE,
        offset: (nextPage - 1) * PAGE_SIZE,
      });
      setMails(r.items);
      setTotal(r.total);
      setPage(nextPage);
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    setSelected(new Set());
    await load(1);
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function togglePage(checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const m of mails) {
        if (checked) next.add(m.id);
        else next.delete(m.id);
      }
      return next;
    });
  }

  async function selectAllFiltered() {
    setBusy(true);
    setError(null);
    try {
      const r = await searchMailIds({ ...filterParams, limit: 2000 });
      setSelected(new Set(r.ids));
      if (r.total > r.ids.length) {
        setInfo(`Se marcaron ${r.ids.length} de ${r.total} (máx. 2000).`);
      } else {
        setInfo(`Se marcaron ${r.ids.length} correo${r.ids.length === 1 ? "" : "s"} filtrados.`);
      }
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al marcar")
      );
    } finally {
      setBusy(false);
    }
  }

  async function openDetail(id: string) {
    setError(null);
    try {
      setDetail(await getArchivedMail(id));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  async function onDownloadEml() {
    if (!detail) return;
    setBusy(true);
    try {
      await downloadEmlToDisk(detail.id);
      setInfo("Descarga EML iniciada");
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al descargar")
      );
    } finally {
      setBusy(false);
    }
  }

  async function onBulkDownload() {
    if (selected.size === 0) return;
    setBusy(true);
    setError(null);
    try {
      await bulkDownloadArchivedMailsToDisk([...selected]);
      setInfo(`Descarga ZIP de ${selected.size} correo(s) iniciada.`);
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al descargar")
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmRestore() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const r = await restoreArchivedMail(detail.id);
      setRestoreOpen(false);
      setDetail(null);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(detail.id);
        return next;
      });
      setInfo(`Restaurado en «${r.folder}» y eliminado del archivo local.`);
      await load(page);
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al restaurar")
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmBulkRestore() {
    if (selected.size === 0) return;
    setBusy(true);
    setError(null);
    try {
      const ids = [...selected];
      const r = await bulkRestoreArchivedMails(ids);
      setBulkRestoreOpen(false);
      setSelected(new Set());
      const failN = r.failed?.length || 0;
      setInfo(
        failN
          ? `Restaurados ${r.restored} de ${r.requested}. Fallaron ${failN}.`
          : `Restaurados ${r.restored} correo(s) y quitados del archivo local.`
      );
      await load(1);
    } catch (err: unknown) {
      setError(
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al restaurar")
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout>
      <Typography variant="h5" sx={{ mb: 0.5 }}>
        Correos archivados
      </Typography>
      <Typography color="text.secondary" variant="body2" sx={{ mb: 1.5 }}>
        Buscá, seleccioná varios para descargar (ZIP) o restaurar. Fechas: original y archivado.
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {info && (
        <Alert severity="success" sx={{ mb: 1 }} onClose={() => setInfo(null)}>
          {info}
        </Alert>
      )}

      <Paper
        component="form"
        onSubmit={onSearch}
        elevation={0}
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          p: 1.25,
          mb: 1,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        <Stack spacing={1}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
            <TextField
              size="small"
              label="Texto"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              fullWidth
              placeholder="asunto, cuerpo…"
              sx={fieldSx}
            />
            <TextField
              size="small"
              label="Remitente"
              value={fromAddress}
              onChange={(e) => setFromAddress(e.target.value)}
              fullWidth
              sx={fieldSx}
            />
            <TextField
              size="small"
              select
              label="Cuenta"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
              sx={{ ...fieldSx, minWidth: { md: 200 } }}
              fullWidth
            >
              <MenuItem value="">Todas</MenuItem>
              {accounts.map((a) => (
                <MenuItem key={a.id} value={a.id}>
                  {a.email}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} flexWrap="wrap">
            <TextField
              size="small"
              label="Desde"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ ...fieldSx, maxWidth: { sm: 150 } }}
            />
            <TextField
              size="small"
              label="Hasta"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ ...fieldSx, maxWidth: { sm: 150 } }}
            />
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={onlyAttachments}
                  onChange={(e) => setOnlyAttachments(e.target.checked)}
                />
              }
              label={<Typography variant="body2">Adjuntos</Typography>}
              sx={{ mr: 1, ml: 0.5 }}
            />
            <Button type="submit" size="small" variant="contained" disabled={loading} sx={{ minWidth: 88 }}>
              {loading ? "…" : "Buscar"}
            </Button>
            <Typography variant="caption" color="text.secondary">
              {total} resultado{total === 1 ? "" : "s"}
              {selected.size > 0 ? ` · ${selected.size} sel.` : ""}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Button size="small" onClick={() => selectAllFiltered()} disabled={busy || total === 0}>
              Marcar todos (filtrados)
            </Button>
            <Button size="small" onClick={() => setSelected(new Set())} disabled={selected.size === 0}>
              Desmarcar
            </Button>
            <Tooltip title="Descargar seleccionados (ZIP)">
              <span>
                <IconButton
                  color="primary"
                  size="small"
                  disabled={selected.size === 0 || busy}
                  onClick={onBulkDownload}
                  aria-label="Descargar masivo"
                >
                  <DownloadIcon />
                </IconButton>
              </span>
            </Tooltip>
            {canRestore && (
              <Tooltip title="Restaurar seleccionados">
                <span>
                  <IconButton
                    color="primary"
                    size="small"
                    disabled={selected.size === 0 || busy}
                    onClick={() => setBulkRestoreOpen(true)}
                    aria-label="Restaurar masivo"
                  >
                    <RestoreIcon />
                  </IconButton>
                </span>
              </Tooltip>
            )}
          </Stack>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
        <TableContainer sx={{ maxHeight: "calc(100vh - 320px)" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ py: 0.5 }}>
                  <Checkbox
                    size="small"
                    checked={pageAllChecked}
                    indeterminate={pageSomeChecked}
                    onChange={(e) => togglePage(e.target.checked)}
                  />
                </TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600 }}>Asunto</TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 160 }}>De</TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 118, whiteSpace: "nowrap" }}>Fecha</TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 118, whiteSpace: "nowrap" }}>Archivado</TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 72 }}>Tam.</TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 40 }} align="center">
                  Adj
                </TableCell>
                <TableCell sx={{ py: 0.75, fontWeight: 600, width: 48 }} align="right">
                  {" "}
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mails.map((m) => (
                <TableRow key={m.id} hover selected={selected.has(m.id)}>
                  <TableCell padding="checkbox" sx={{ py: 0.5 }}>
                    <Checkbox size="small" checked={selected.has(m.id)} onChange={() => toggle(m.id)} />
                  </TableCell>
                  <TableCell sx={{ py: 0.5, maxWidth: 0 }}>
                    <Typography variant="body2" noWrap title={m.subject || "(sin asunto)"}>
                      {m.subject || "(sin asunto)"}
                    </Typography>
                    {m.body_preview && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        display="block"
                        noWrap
                        title={m.body_preview}
                      >
                        {m.body_preview}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <Typography variant="caption" noWrap display="block" title={m.from_address}>
                      {m.from_address}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ py: 0.5, whiteSpace: "nowrap" }}>
                    <Typography variant="caption">{formatDateTimeShort(m.sent_at)}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 0.5, whiteSpace: "nowrap" }}>
                    <Typography variant="caption">{formatDateTimeShort(m.archived_at)}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <Typography variant="caption">{formatBytes(m.size_bytes)}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }} align="center">
                    <Typography variant="caption">{m.has_attachments ? "Sí" : "—"}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }} align="right">
                    <Tooltip title="Ver">
                      <IconButton size="small" onClick={() => openDetail(m.id)} aria-label="Ver">
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {mails.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8}>
                    <Typography color="text.secondary" variant="body2">
                      No hay correos archivados.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {total > PAGE_SIZE && (
          <Stack direction="row" justifyContent="center" sx={{ py: 1 }}>
            <Pagination
              size="small"
              count={pageCount}
              page={page}
              onChange={(_, p) => load(p)}
              disabled={loading}
              color="primary"
            />
          </Stack>
        )}
      </Paper>

      <Dialog
        open={!!detail}
        onClose={() => setDetail(null)}
        fullWidth
        maxWidth="lg"
        PaperProps={{ sx: { minHeight: "82vh" } }}
      >
        <DialogTitle sx={{ py: 1.5, pr: 6 }}>{detail?.subject || "(sin asunto)"}</DialogTitle>
        <DialogContent dividers sx={{ pt: 1.5 }}>
          {detail && (
            <Stack spacing={1.5}>
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
                    <strong>Para:</strong> {detail.to_addresses || "—"}
                  </Typography>
                  {detail.cc_addresses && (
                    <Typography variant="body2">
                      <strong>CC:</strong> {detail.cc_addresses}
                    </Typography>
                  )}
                  <Typography variant="body2">
                    <strong>Carpeta:</strong> {detail.folder_path || "—"}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    <strong>Fecha mail:</strong> {formatDateTime(detail.sent_at || detail.received_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Archivado:</strong> {formatDateTime(detail.archived_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Tamaño:</strong> {formatBytes(detail.size_bytes)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>SHA256:</strong> {detail.content_sha256?.slice(0, 16)}…
                  </Typography>
                </Box>
              </Box>
              {detail.deleted_from_provider && (
                <Alert severity="warning">Fue borrado del proveedor al archivar.</Alert>
              )}
              {detail.restored_at && (
                <Alert severity="info">Restaurado el {formatDateTime(detail.restored_at)}</Alert>
              )}
              <Divider />
              <MailBodyViewer
                text={detail.body_text}
                html={detail.body_html}
                isHtml={detail.body_is_html}
                minHeight={480}
                maxHeight="62vh"
              />
              {detail.attachments?.length > 0 && (
                <>
                  <Typography variant="subtitle2">Adjuntos</Typography>
                  <Stack spacing={0.5}>
                    {detail.attachments.map((a) => (
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
                                await downloadAttachmentToDisk(detail.id, a.id);
                              } catch (err: unknown) {
                                setError(
                                  String(
                                    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                                      "Error adjunto"
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
                </>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Tooltip title="Cerrar">
            <IconButton onClick={() => setDetail(null)} aria-label="Cerrar">
              <CloseIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Descargar EML">
            <span>
              <IconButton onClick={onDownloadEml} disabled={busy} aria-label="Descargar EML">
                <DownloadIcon />
              </IconButton>
            </span>
          </Tooltip>
          {canRestore && (
            <Tooltip title="Restaurar al proveedor">
              <span>
                <IconButton
                  color="primary"
                  onClick={() => setRestoreOpen(true)}
                  disabled={busy}
                  aria-label="Restaurar al proveedor"
                >
                  <RestoreIcon />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={restoreOpen}
        title="Restaurar correo"
        message={`Se restaurará «${detail?.subject || "(sin asunto)"}» en la carpeta MailArchive y se eliminará del archivo local.`}
        confirmLabel="Restaurar y quitar del archivo"
        confirmColor="primary"
        loading={busy}
        onCancel={() => !busy && setRestoreOpen(false)}
        onConfirm={confirmRestore}
      />

      <ConfirmDialog
        open={bulkRestoreOpen}
        title="Restaurar seleccionados"
        message={`Se restaurarán ${selected.size} correo(s) en MailArchive y se eliminarán del archivo local. ¿Continuar?`}
        confirmLabel="Restaurar seleccionados"
        confirmColor="primary"
        loading={busy}
        onCancel={() => !busy && setBulkRestoreOpen(false)}
        onConfirm={confirmBulkRestore}
      />
    </AppLayout>
  );
}
