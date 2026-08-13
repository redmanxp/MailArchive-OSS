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
import PageShell from "../components/PageShell";
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
import { useLocale } from "../i18n/LocaleContext";
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
  const { t, tf } = useLocale();
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
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("bulkPreview", "openError")
        )
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
      navigate("/app/jobs", { replace: true, state: { startedJobId: job.id } });
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("bulkPreview", "startError")
        )
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
  const noSubject = t("bulkPreview", "noSubject");
  const subtitle = payload.account_email
    ? `${t("bulkPreview", "subtitle")} · ${payload.account_email}`
    : t("bulkPreview", "subtitle");

  return (
    <AppLayout>
      <BulkPreparingModal
        open={loading}
        title={t("bulkPreview", "modalTitle")}
        message={t("bulkPreview", "modalBody")}
        showCancel={false}
      />
      <PageShell
        title={t("bulkPreview", "title")}
        subtitle={subtitle}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title={t("common", "back")}>
              <IconButton onClick={() => navigate("/app/bulk")} aria-label={t("common", "back")}>
                <ArrowBackIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("bulkPreview", "start")}>
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
                  {loading ? t("bulkPreview", "starting") : t("bulkPreview", "start")}
                </Button>
              </span>
            </Tooltip>
          </Stack>
        }
        alerts={
          error ? (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          ) : null
        }
        filters={
          <Paper sx={{ p: 1.25 }} elevation={0} variant="outlined">
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
              <Typography variant="body2" sx={{ flex: 1 }}>
                {tf("bulkPreview", "selected", { n: selected.size })} / {payload.messages.length} ·{" "}
                {formatBytes(selectedBytes)}
                {" · "}
                {payload.delete_after_archive
                  ? t("bulkPreview", "willDelete")
                  : t("bulkPreview", "willKeep")}
              </Typography>
              <Button size="small" onClick={() => toggleAll(true)} disabled={allChecked}>
                {t("bulkPreview", "selectAll")}
              </Button>
              <Button size="small" onClick={() => toggleAll(false)} disabled={selected.size === 0}>
                {t("bulkPreview", "deselectAll")}
              </Button>
            </Stack>
          </Paper>
        }
        footer={
          payload.messages.length > PAGE_SIZE ? (
            <Stack direction="row" justifyContent="center">
              <Pagination
                size="small"
                count={pageCount}
                page={page}
                onChange={(_, p) => setPage(p)}
                color="primary"
              />
            </Stack>
          ) : null
        }
      >
        <Paper elevation={0} variant="outlined">
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={pageAllChecked}
                      indeterminate={pageSomeChecked}
                      onChange={(e) => togglePage(e.target.checked)}
                    />
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulkPreview", "subject")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulkPreview", "from")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulkPreview", "date")}</TableCell>
                  <TableCell sx={{ fontWeight: 600, width: 72 }} align="center">
                    {t("bulkPreview", "attachments")}
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulkPreview", "size")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">
                    {t("bulkPreview", "view")}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageRows.map((m) => (
                  <TableRow key={m.id} hover selected={selected.has(m.id)}>
                    <TableCell padding="checkbox">
                      <Checkbox checked={selected.has(m.id)} onChange={() => toggle(m.id)} />
                    </TableCell>
                    <TableCell>{m.subject || noSubject}</TableCell>
                    <TableCell>{m.from_address}</TableCell>
                    <TableCell>{formatDateTime(m.received_at || m.sent_at)}</TableCell>
                    <TableCell align="center">
                      {m.has_attachments ? t("common", "yes") : t("common", "emptyDash")}
                    </TableCell>
                    <TableCell>{formatBytes(m.size_bytes || 0)}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t("bulkPreview", "view")}>
                        <IconButton
                          size="small"
                          onClick={() => onView(m)}
                          disabled={detailLoading}
                          aria-label={t("bulkPreview", "view")}
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </PageShell>

      <ConfirmDialog
        open={confirm}
        title={t("bulkPreview", "confirmTitle")}
        message={
          payload.delete_after_archive
            ? `${tf("bulkPreview", "selected", { n: selected.size })} (${formatBytes(selectedBytes)}). ${t("bulkPreview", "confirmDelete")}`
            : `${tf("bulkPreview", "selected", { n: selected.size })} (${formatBytes(selectedBytes)}). ${t("bulkPreview", "confirmKeep")}`
        }
        confirmLabel={t("bulkPreview", "confirmApply")}
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
        <DialogTitle sx={{ py: 1.5 }}>{detail?.subject || noSubject}</DialogTitle>
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
                    <strong>{t("bulkPreview", "from")}:</strong> {detail.from_address}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulkPreview", "to")}:</strong>{" "}
                    {(detail.to_addresses || []).join(", ") || t("common", "emptyDash")}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    <strong>{t("bulkPreview", "date")}:</strong>{" "}
                    {formatDateTime(detail.received_at || detail.sent_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulkPreview", "size")}:</strong> {formatBytes(detail.size_bytes || 0)}
                    {detail.attachments?.length || detail.has_attachments
                      ? ` · ${detail.attachments?.length || t("common", "yes")} ${t("bulkPreview", "attachmentCount")}`
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
                    {t("bulkPreview", "attachmentsTitle")}
                  </Typography>
                  <Stack spacing={0.5}>
                    {detail.attachments!.map((a) => (
                      <Stack key={a.id} direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2">
                          {a.filename} ({formatBytes(a.size_bytes)})
                        </Typography>
                        <Tooltip title={t("bulkPreview", "downloadAttachment")}>
                          <IconButton
                            size="small"
                            aria-label={t("bulkPreview", "downloadAttachment")}
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
                                      ?.detail || t("bulkPreview", "downloadError")
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
                {t("common", "close")}
              </Button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
