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
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import DownloadIcon from "@mui/icons-material/Download";
import RestoreIcon from "@mui/icons-material/Restore";
import VisibilityIcon from "@mui/icons-material/Visibility";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import ConfirmDialog from "../components/ConfirmDialog";
import MailBodyViewer from "../components/MailBodyViewer";
import { useAuth } from "../auth/AuthContext";
import { useLocale } from "../i18n/LocaleContext";
import {
  bulkDeleteArchivedMails,
  bulkDownloadArchivedMailsToDisk,
  bulkRestoreArchivedMails,
  deleteArchivedMail,
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
  const { t, tf } = useLocale();
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
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [keepCopy, setKeepCopy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const canRestore = user?.role !== "readonly";
  const canDelete = user?.role !== "readonly";
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const noSubject = t("mails", "noSubject", "(sin asunto)");
  const accountLabelById = useMemo(() => {
    const map = new Map<number, string>();
    for (const a of accounts) {
      map.set(a.id, a.email || a.display_name || `#${a.id}`);
    }
    return map;
  }, [accounts]);

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
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
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
        setInfo(tf("mails", "markedPartial", { n: r.ids.length, total: r.total }));
      } else {
        setInfo(tf("mails", "markedAll", { n: r.ids.length }));
      }
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "markError")
        )
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
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
    }
  }

  async function onDownloadEml() {
    if (!detail) return;
    setBusy(true);
    try {
      await downloadEmlToDisk(detail.id);
      setInfo(t("mails", "emlStarted"));
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "downloadError")
        )
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
      setInfo(tf("mails", "zipStarted", { n: selected.size }));
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "downloadError")
        )
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
      const kept = keepCopy;
      const r = await restoreArchivedMail(detail.id, { keep_copy: kept });
      setRestoreOpen(false);
      setKeepCopy(false);
      if (kept) {
        const refreshed = await getArchivedMail(detail.id);
        setDetail(refreshed);
        setInfo(tf("mails", "restoredOneKept", { folder: r.folder }));
      } else {
        setDetail(null);
        setSelected((prev) => {
          const next = new Set(prev);
          next.delete(detail.id);
          return next;
        });
        setInfo(tf("mails", "restoredOne", { folder: r.folder }));
      }
      await load(page);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "restoreError")
        )
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
      const kept = keepCopy;
      const ids = [...selected];
      const r = await bulkRestoreArchivedMails(ids, kept);
      setBulkRestoreOpen(false);
      setKeepCopy(false);
      setSelected(new Set());
      const failN = r.failed?.length || 0;
      setInfo(
        failN
          ? tf("mails", "restoredPartial", { ok: r.restored, total: r.requested, fail: failN })
          : kept
            ? tf("mails", "restoredBulkKept", { n: r.restored })
            : tf("mails", "restoredBulk", { n: r.restored })
      );
      await load(1);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "restoreError")
        )
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      await deleteArchivedMail(detail.id);
      setDeleteOpen(false);
      setDetail(null);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(detail.id);
        return next;
      });
      setInfo(t("mails", "deletedOne"));
      await load(page);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "deleteError")
        )
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmBulkDelete() {
    if (selected.size === 0) return;
    setBusy(true);
    setError(null);
    try {
      const ids = [...selected];
      const r = await bulkDeleteArchivedMails(ids);
      setBulkDeleteOpen(false);
      setSelected(new Set());
      if (detail && ids.includes(detail.id)) setDetail(null);
      const failN = r.failed?.length || 0;
      setInfo(
        failN
          ? tf("mails", "deletedPartial", { ok: r.deleted, total: r.requested, fail: failN })
          : tf("mails", "deletedBulk", { n: r.deleted })
      );
      await load(1);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("mails", "deleteError")
        )
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout>
      <PageShell
        title={t("mails", "title")}
        subtitle={t("mails", "subtitle")}
        alerts={
          <>
            {error && (
              <Alert severity="error" onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            {info && (
              <Alert severity="success" onClose={() => setInfo(null)} sx={{ mt: error ? 1 : 0 }}>
                {info}
              </Alert>
            )}
          </>
        }
        filters={
          <Paper
            component="form"
            onSubmit={onSearch}
            elevation={0}
            sx={{
              p: 1.25,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <Stack spacing={1}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                <TextField
                  size="small"
                  label={t("mails", "text")}
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  fullWidth
                  placeholder={t("mails", "textPlaceholder")}
                  sx={fieldSx}
                />
                <TextField
                  size="small"
                  label={t("mails", "from")}
                  value={fromAddress}
                  onChange={(e) => setFromAddress(e.target.value)}
                  fullWidth
                  sx={fieldSx}
                />
                <TextField
                  size="small"
                  select
                  label={t("mails", "account")}
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
                  sx={{ ...fieldSx, minWidth: { md: 200 } }}
                  fullWidth
                >
                  <MenuItem value="">{t("common", "all")}</MenuItem>
                  {accounts.map((a) => (
                    <MenuItem key={a.id} value={a.id}>
                      {a.email}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1}
                alignItems={{ sm: "center" }}
                flexWrap="wrap"
              >
                <TextField
                  size="small"
                  label={t("mails", "dateFrom")}
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ ...fieldSx, maxWidth: { sm: 150 } }}
                />
                <TextField
                  size="small"
                  label={t("mails", "dateTo")}
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
                  label={<Typography variant="body2">{t("mails", "attachmentsOnly")}</Typography>}
                  sx={{ mr: 1, ml: 0.5 }}
                />
                <Button type="submit" size="small" variant="contained" disabled={loading} sx={{ minWidth: 88 }}>
                  {loading ? "…" : t("common", "search")}
                </Button>
                <Typography variant="caption" color="text.secondary">
                  {tf("mails", "results", { total, selected: selected.size })}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Button size="small" onClick={() => selectAllFiltered()} disabled={busy || total === 0}>
                  {t("mails", "selectFiltered")}
                </Button>
                <Button size="small" onClick={() => setSelected(new Set())} disabled={selected.size === 0}>
                  {t("mails", "deselect")}
                </Button>
                <Tooltip title={t("mails", "downloadZip")}>
                  <span>
                    <IconButton
                      color="primary"
                      size="small"
                      disabled={selected.size === 0 || busy}
                      onClick={onBulkDownload}
                      aria-label={t("mails", "downloadZip")}
                    >
                      <DownloadIcon />
                    </IconButton>
                  </span>
                </Tooltip>
                {canRestore && (
                  <Tooltip title={t("mails", "restoreSelected")}>
                    <span>
                      <IconButton
                        color="primary"
                        size="small"
                        disabled={selected.size === 0 || busy}
                        onClick={() => {
                          setKeepCopy(false);
                          setBulkRestoreOpen(true);
                        }}
                        aria-label={t("mails", "restoreSelected")}
                      >
                        <RestoreIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                )}
                {canDelete && (
                  <Tooltip title={t("mails", "deleteSelected")}>
                    <span>
                      <IconButton
                        color="error"
                        size="small"
                        disabled={selected.size === 0 || busy}
                        onClick={() => setBulkDeleteOpen(true)}
                        aria-label={t("mails", "deleteSelected")}
                      >
                        <DeleteForeverIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                )}
              </Stack>
            </Stack>
          </Paper>
        }
        footer={
          total > PAGE_SIZE ? (
            <Stack direction="row" justifyContent="center">
              <Pagination
                size="small"
                count={pageCount}
                page={page}
                onChange={(_, p) => load(p)}
                disabled={loading}
                color="primary"
              />
            </Stack>
          ) : null
        }
      >
        <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
          <TableContainer>
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
                  <TableCell sx={{ py: 0.75, fontWeight: 600 }}>{t("mails", "subject")}</TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 180 }}>{t("mails", "accountCol")}</TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 160 }}>{t("mails", "fromCol")}</TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 118, whiteSpace: "nowrap" }}>
                    {t("mails", "date")}
                  </TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 118, whiteSpace: "nowrap" }}>
                    {t("mails", "archivedAt")}
                  </TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 72 }}>{t("mails", "size")}</TableCell>
                  <TableCell sx={{ py: 0.75, fontWeight: 600, width: 40 }} align="center">
                    {t("mails", "att")}
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
                      <Typography variant="body2" noWrap title={m.subject || noSubject}>
                        {m.subject || noSubject}
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
                      <Typography
                        variant="caption"
                        noWrap
                        display="block"
                        title={accountLabelById.get(m.account_id) || String(m.account_id)}
                      >
                        {accountLabelById.get(m.account_id) || `#${m.account_id}`}
                      </Typography>
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
                      <Typography variant="caption">
                        {m.has_attachments ? t("common", "yes") : t("common", "emptyDash")}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ py: 0.5 }} align="right">
                      <Tooltip title={t("mails", "view", "Ver")}>
                        <IconButton
                          size="small"
                          onClick={() => openDetail(m.id)}
                          aria-label={t("mails", "view", "Ver")}
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {mails.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9}>
                      <Typography color="text.secondary" variant="body2">
                        {t("mails", "empty")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </PageShell>

      <Dialog
        open={!!detail}
        onClose={() => setDetail(null)}
        fullWidth
        maxWidth="lg"
        PaperProps={{ sx: { minHeight: "82vh" } }}
      >
        <DialogTitle sx={{ py: 1.5, pr: 6 }}>{detail?.subject || noSubject}</DialogTitle>
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
                    <strong>{t("mails", "accountCol")}:</strong>{" "}
                    {accountLabelById.get(detail.account_id) || `#${detail.account_id}`}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("mails", "fromCol")}:</strong> {detail.from_address}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("mails", "to")}:</strong> {detail.to_addresses || t("common", "emptyDash")}
                  </Typography>
                  {detail.cc_addresses && (
                    <Typography variant="body2">
                      <strong>{t("mails", "cc")}:</strong> {detail.cc_addresses}
                    </Typography>
                  )}
                  <Typography variant="body2">
                    <strong>{t("mails", "folder")}:</strong> {detail.folder_path || t("common", "emptyDash")}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    <strong>{t("mails", "mailDate")}:</strong>{" "}
                    {formatDateTime(detail.sent_at || detail.received_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("mails", "archivedAt")}:</strong> {formatDateTime(detail.archived_at)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("mails", "size")}:</strong> {formatBytes(detail.size_bytes)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("mails", "sha256")}:</strong> {detail.content_sha256?.slice(0, 16)}…
                  </Typography>
                </Box>
              </Box>
              {detail.deleted_from_provider && (
                <Alert severity="warning">{t("mails", "wasDeleted")}</Alert>
              )}
              {detail.restored_at && (
                <Alert severity="info">
                  {tf("mails", "restoredAt", { date: formatDateTime(detail.restored_at) })}
                </Alert>
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
                  <Typography variant="subtitle2">{t("mails", "attachments")}</Typography>
                  <Stack spacing={0.5}>
                    {detail.attachments.map((a) => (
                      <Stack key={a.id} direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2">
                          {a.filename} ({formatBytes(a.size_bytes)})
                        </Typography>
                        <Tooltip title={t("mails", "downloadAttachment", "Descargar adjunto")}>
                          <IconButton
                            size="small"
                            aria-label={t("mails", "downloadAttachment", "Descargar adjunto")}
                            onClick={async () => {
                              try {
                                await downloadAttachmentToDisk(detail.id, a.id);
                              } catch (err: unknown) {
                                setError(
                                  String(
                                    (err as { response?: { data?: { detail?: string } } })?.response?.data
                                      ?.detail || t("mails", "attachmentError", "Error adjunto")
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
          <Tooltip title={t("common", "close")}>
            <IconButton onClick={() => setDetail(null)} aria-label={t("common", "close")}>
              <CloseIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={t("mails", "downloadEml")}>
            <span>
              <IconButton onClick={onDownloadEml} disabled={busy} aria-label={t("mails", "downloadEml")}>
                <DownloadIcon />
              </IconButton>
            </span>
          </Tooltip>
          {canRestore && (
            <Tooltip title={t("mails", "restore")}>
              <span>
                <IconButton
                  color="primary"
                  onClick={() => {
                    setKeepCopy(false);
                    setRestoreOpen(true);
                  }}
                  disabled={busy}
                  aria-label={t("mails", "restore")}
                >
                  <RestoreIcon />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {canDelete && (
            <Tooltip title={t("mails", "deleteFromArchive")}>
              <span>
                <IconButton
                  color="error"
                  onClick={() => setDeleteOpen(true)}
                  disabled={busy}
                  aria-label={t("mails", "deleteFromArchive")}
                >
                  <DeleteForeverIcon />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={restoreOpen}
        title={t("mails", "restoreTitle")}
        message={
          keepCopy ? t("mails", "restoreMessageKeep") : t("mails", "restoreMessage")
        }
        confirmLabel={
          keepCopy ? t("mails", "restoreConfirmKeep") : t("mails", "restoreConfirm")
        }
        confirmColor="primary"
        loading={busy}
        onCancel={() => {
          if (!busy) {
            setRestoreOpen(false);
            setKeepCopy(false);
          }
        }}
        onConfirm={confirmRestore}
      >
        <FormControlLabel
          sx={{ mt: 1.5, alignItems: "flex-start" }}
          control={
            <Checkbox
              checked={keepCopy}
              onChange={(e) => setKeepCopy(e.target.checked)}
              disabled={busy}
              size="small"
            />
          }
          label={
            <Box>
              <Typography variant="body2">{t("mails", "keepCopyLabel")}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t("mails", "keepCopyHint")}
              </Typography>
            </Box>
          }
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={bulkRestoreOpen}
        title={t("mails", "bulkRestoreTitle")}
        message={
          keepCopy
            ? tf("mails", "bulkRestoreMessageKeep", { n: selected.size })
            : tf("mails", "bulkRestoreMessage", { n: selected.size })
        }
        confirmLabel={t("mails", "restoreSelected")}
        confirmColor="primary"
        loading={busy}
        onCancel={() => {
          if (!busy) {
            setBulkRestoreOpen(false);
            setKeepCopy(false);
          }
        }}
        onConfirm={confirmBulkRestore}
      >
        <FormControlLabel
          sx={{ mt: 1.5, alignItems: "flex-start" }}
          control={
            <Checkbox
              checked={keepCopy}
              onChange={(e) => setKeepCopy(e.target.checked)}
              disabled={busy}
              size="small"
            />
          }
          label={
            <Box>
              <Typography variant="body2">{t("mails", "keepCopyLabel")}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t("mails", "keepCopyHint")}
              </Typography>
            </Box>
          }
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteOpen}
        title={t("mails", "deleteTitle")}
        message={t("mails", "deleteMessage")}
        confirmLabel={t("mails", "deleteConfirm")}
        confirmColor="error"
        loading={busy}
        onCancel={() => {
          if (!busy) setDeleteOpen(false);
        }}
        onConfirm={confirmDelete}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        title={t("mails", "bulkDeleteTitle")}
        message={tf("mails", "bulkDeleteMessage", { n: selected.size })}
        confirmLabel={t("mails", "deleteSelected")}
        confirmColor="error"
        loading={busy}
        onCancel={() => {
          if (!busy) setBulkDeleteOpen(false);
        }}
        onConfirm={confirmBulkDelete}
      />
    </AppLayout>
  );
}
