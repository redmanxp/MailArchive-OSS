import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Alert,
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
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import ReplayIcon from "@mui/icons-material/Replay";
import StopIcon from "@mui/icons-material/Stop";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import BulkPreparingModal from "../components/BulkPreparingModal";
import {
  cancelArchiveJob,
  getArchiveJob,
  listAccountFolders,
  listAccounts,
  listArchiveJobs,
  retryArchiveJob,
  simulateBulkArchive,
  type AccountPublic,
  type ArchiveJob,
  type FolderPublic,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { formatDateTime } from "../utils/datetime";
import { folderDepth, folderLeafName } from "../utils/folders";
import { useLabels } from "../utils/labels";
import { saveBulkPreview } from "./BulkPreviewPage";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function BulkArchivePage() {
  const { t, tf } = useLocale();
  const { jobStatusLabel } = useLabels();
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
    listAccounts({ status: "active" })
      .then((rows) => {
        setAccounts(rows);
        if (rows.length === 1) setAccountId(rows[0].id);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("bulk", "loadError"))));
    refreshJobs().catch(() => undefined);
  }, [t]);

  useEffect(() => {
    const started = (location.state as { startedJobId?: number } | null)?.startedJobId;
    if (started) {
      setInfo(tf("bulk", "jobStarted", { id: started }));
      navigate("/app/bulk", { replace: true, state: {} });
      refreshJobs().catch(() => undefined);
    }
  }, [location.state, navigate, tf]);

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
      .catch((e) => setError(String(e?.response?.data?.detail || t("bulk", "loadError"))));
  }, [accountId, t]);

  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === "pending" || j.status === "running");
    if (!hasRunning) return;
    const timer = setInterval(() => {
      refreshJobs().catch(() => undefined);
    }, 2500);
    return () => clearInterval(timer);
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
    const rows = await listArchiveJobs();
    setJobs(rows);
    if (rows.some((j) => j.status === "failed")) {
      setShowJobHistory(true);
    }
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
        setInfo(t("bulk", "simZero"));
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
        setInfo(t("bulk", "prepCancelled"));
        return;
      }
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
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
      <BulkPreparingModal open={loading} cancelling={cancellingPrep} onCancel={onCancelPrep} />
      <PageShell
        title={t("bulk", "title")}
        subtitle={t("bulk", "subtitle")}
        actions={
          <Tooltip title={t("common", "refresh")}>
            <IconButton onClick={() => refreshJobs()} color="primary" aria-label={t("common", "refresh")}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        }
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
          <Paper sx={{ p: 3 }} component="form" onSubmit={onSimulate} elevation={0} variant="outlined">
            <Stack spacing={2}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <TextField
                  select
                  label={t("bulk", "account")}
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
                  label={t("bulk", "folder")}
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
                  label={t("bulk", "dateFrom")}
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />
                <TextField
                  label={t("bulk", "dateTo")}
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />
                <TextField
                  label={t("bulk", "olderThan")}
                  type="number"
                  value={olderDays}
                  onChange={(e) => setOlderDays(e.target.value)}
                  fullWidth
                />
              </Stack>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                <TextField
                  label={t("bulk", "minSize")}
                  type="number"
                  value={minSizeMb}
                  onChange={(e) => setMinSizeMb(e.target.value)}
                  fullWidth
                />
                <TextField
                  label={t("bulk", "limit")}
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
                  helperText={t("bulk", "limitHint")}
                  fullWidth
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={onlyAttachments}
                      onChange={(e) => setOnlyAttachments(e.target.checked)}
                    />
                  }
                  label={t("bulk", "onlyAttachments")}
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
                label={t("bulk", "deleteFromProvider")}
              />
              <Stack direction="row" spacing={1} alignItems="center">
                <Tooltip title={t("bulk", "startTooltip")}>
                  <span>
                    <Button
                      type="submit"
                      variant="contained"
                      size="large"
                      disabled={!accountId || loading}
                      sx={{ px: 3, py: 1.25, fontSize: "1rem", fontWeight: 600 }}
                    >
                      {loading ? t("bulk", "preparing") : t("bulk", "start")}
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </Stack>
          </Paper>
        }
      >
        <Paper elevation={0} variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }} spacing={1}>
            <Typography variant="h6">{t("bulk", "jobsTitle")}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ flex: 1, textAlign: "right" }}>
              {t("bulk", "jobsHint")}
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={showJobHistory}
                  onChange={(e) => setShowJobHistory(e.target.checked)}
                />
              }
              label={<Typography variant="body2">{t("bulk", "history")}</Typography>}
            />
          </Stack>
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "jobId")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "jobStatus")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "progress")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "archived")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "created")}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {t("bulk", "actions")}
                  </TableCell>
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
                        color={
                          j.status === "failed" ? "error" : j.status === "completed" ? "success" : "primary"
                        }
                      />
                    </TableCell>
                    <TableCell>
                      {tf("bulk", "jobStatsLine", {
                        ok: j.archived_messages,
                        skip: j.skipped_messages,
                        err: j.failed_messages,
                      })}
                      <Typography variant="caption" display="block">
                        {formatBytes(j.archived_bytes)} / {formatBytes(j.total_bytes)}
                      </Typography>
                      {j.error_message ? (
                        <Typography variant="caption" display="block" color="error" sx={{ mt: 0.25 }}>
                          {j.error_message}
                        </Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>{formatDateTime(j.created_at)}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t("common", "refresh")}>
                        <IconButton
                          size="small"
                          aria-label={t("common", "refresh")}
                          onClick={async () => {
                            const fresh = await getArchiveJob(j.id);
                            setJobs((prev) => prev.map((x) => (x.id === j.id ? fresh : x)));
                          }}
                        >
                          <RefreshIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      {(j.status === "failed" || j.status === "cancelled") && (
                        <Tooltip title={t("bulk", "retry")}>
                          <IconButton
                            size="small"
                            color="primary"
                            aria-label={t("bulk", "retry")}
                            onClick={async () => {
                              try {
                                setShowJobHistory(true);
                                await retryArchiveJob(j.id);
                                await refreshJobs();
                              } catch (err: unknown) {
                                setError(
                                  String(
                                    (err as { response?: { data?: { detail?: string } } })?.response
                                      ?.data?.detail || t("common", "error")
                                  )
                                );
                              }
                            }}
                          >
                            <ReplayIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                      {(j.status === "pending" || j.status === "running") && (
                        <Tooltip title={t("common", "cancel")}>
                          <IconButton
                            size="small"
                            color="warning"
                            aria-label={t("common", "cancel")}
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
                        {showJobHistory ? t("bulk", "noJobs") : t("bulk", "noJobsHint")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </PageShell>
    </AppLayout>
  );
}
