import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
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
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import ReplayIcon from "@mui/icons-material/Replay";
import StopIcon from "@mui/icons-material/Stop";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import {
  cancelArchiveJob,
  getArchiveJob,
  listArchiveJobs,
  retryArchiveJob,
  type ArchiveJob,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { formatDateTime } from "../utils/datetime";
import { useLabels } from "../utils/labels";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function criteriaSourceLabel(criteria: Record<string, unknown> | null | undefined, t: (ns: string, k: string) => string) {
  const src = String(criteria?.source || "");
  if (src === "scheduled_incremental") return t("bulk", "sourceScheduled");
  if (src) return src;
  return t("bulk", "sourceManual");
}

function isQuotaJob(j: ArchiveJob) {
  const src = String(j.criteria?.source || "");
  return src === "scheduled_incremental" || Boolean(j.criteria?.historical_backfill);
}

const PAGE_SIZE = 25;

function jobProgressIndeterminate(j: ArchiveJob) {
  const running = j.status === "running" || j.status === "pending";
  if (!running) return false;
  if (!j.total_messages) return true;
  return isQuotaJob(j) && j.archived_messages === 0 && j.processed_messages > 0;
}

export default function JobsPage() {
  const { t, tf } = useLocale();
  const { jobStatusLabel } = useLabels();
  const navigate = useNavigate();
  const location = useLocation();
  const [jobs, setJobs] = useState<ArchiveJob[]>([]);
  const [showJobHistory, setShowJobHistory] = useState(true);
  const [page, setPage] = useState(1);
  const [detailJob, setDetailJob] = useState<ArchiveJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const visibleJobs = showJobHistory
    ? jobs
    : jobs.filter((j) => j.status === "pending" || j.status === "running");
  const pageCount = Math.max(1, Math.ceil(visibleJobs.length / PAGE_SIZE));
  const pageRows = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return visibleJobs.slice(start, start + PAGE_SIZE);
  }, [visibleJobs, page]);

  async function refreshJobs() {
    const rows = await listArchiveJobs();
    setJobs(rows);
  }

  useEffect(() => {
    refreshJobs().catch(() => undefined);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [showJobHistory]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  useEffect(() => {
    const started = (location.state as { startedJobId?: number } | null)?.startedJobId;
    if (started) {
      setInfo(tf("bulk", "jobStarted", { id: started }));
      navigate("/app/jobs", { replace: true, state: {} });
      refreshJobs().catch(() => undefined);
    }
  }, [location.state, navigate, tf]);

  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === "pending" || j.status === "running");
    const timer = setInterval(() => {
      refreshJobs().catch(() => undefined);
    }, hasRunning ? 2500 : 10000);
    return () => clearInterval(timer);
  }, [jobs]);

  return (
    <AppLayout>
      <PageShell
        title={t("nav", "jobs", "Procesos")}
        subtitle={t("bulk", "jobsHint")}
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
        footer={
          visibleJobs.length > PAGE_SIZE ? (
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
        <Paper elevation={0} variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="flex-end" sx={{ mb: 1 }} spacing={1}>
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
                  <TableCell sx={{ fontWeight: 600 }}>{t("bulk", "jobAccount")}</TableCell>
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
                {pageRows.map((j) => (
                  <TableRow key={j.id}>
                    <TableCell>#{j.id}</TableCell>
                    <TableCell>
                      <Typography variant="body2" noWrap title={j.account_email || undefined}>
                        {j.account_email || `#${j.account_id}`}
                      </Typography>
                    </TableCell>
                    <TableCell>{jobStatusLabel(j.status)}</TableCell>
                    <TableCell sx={{ minWidth: 200 }}>
                      <Typography variant="caption">
                        {isQuotaJob(j) || !j.total_messages
                          ? j.total_messages
                            ? tf(
                                "bulk",
                                "jobProgressQuota",
                                {
                                  archived: j.archived_messages,
                                  total: j.total_messages,
                                  pct: j.progress_pct,
                                  scanned: j.processed_messages,
                                },
                                "{archived}/{total} archivados ({pct}%) · {scanned} revisados"
                              )
                            : tf(
                                "bulk",
                                "jobProgressUnknown",
                                { scanned: j.processed_messages },
                                "{scanned} revisados"
                              )
                          : `${j.processed_messages}/${j.total_messages} (${j.progress_pct}%)`}
                      </Typography>
                      <LinearProgress
                        variant={jobProgressIndeterminate(j) ? "indeterminate" : "determinate"}
                        value={jobProgressIndeterminate(j) ? undefined : Math.min(100, j.progress_pct)}
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
                      <Tooltip title={t("bulk", "jobDetail")}>
                        <IconButton
                          size="small"
                          aria-label={t("bulk", "jobDetail")}
                          onClick={async () => {
                            try {
                              const fresh = await getArchiveJob(j.id);
                              setJobs((prev) => prev.map((x) => (x.id === j.id ? fresh : x)));
                              setDetailJob(fresh);
                            } catch {
                              setDetailJob(j);
                            }
                          }}
                        >
                          <InfoOutlinedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
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
                    <TableCell colSpan={7}>
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

        <Dialog open={detailJob != null} onClose={() => setDetailJob(null)} fullWidth maxWidth="md">
          <DialogTitle>
            {tf("bulk", "jobDetailTitle", { id: String(detailJob?.id ?? "") })}
          </DialogTitle>
          <DialogContent dividers>
            {detailJob && (
              <Stack spacing={2}>
                <Stack spacing={0.5}>
                  <Typography variant="body2">
                    <strong>{t("bulk", "jobAccount")}:</strong>{" "}
                    {detailJob.account_email || `#${detailJob.account_id}`}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulk", "jobStatus")}:</strong> {jobStatusLabel(detailJob.status)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulk", "jobSource")}:</strong>{" "}
                    {criteriaSourceLabel(detailJob.criteria, t)}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulk", "created")}:</strong> {formatDateTime(detailJob.created_at)}
                    {detailJob.started_at ? ` · ${t("bulk", "started")}: ${formatDateTime(detailJob.started_at)}` : ""}
                    {detailJob.finished_at
                      ? ` · ${t("bulk", "finished")}: ${formatDateTime(detailJob.finished_at)}`
                      : ""}
                  </Typography>
                  <Typography variant="body2">
                    <strong>{t("bulk", "deleteFromProvider")}:</strong>{" "}
                    {detailJob.delete_after_archive ? t("common", "yes") : t("common", "no")}
                  </Typography>
                </Stack>

                <Alert severity="info" variant="outlined">
                  {tf("bulk", "jobResultSummary", {
                    archived: detailJob.result?.archived ?? detailJob.archived_messages,
                    skipped:
                      detailJob.result?.skipped_already_archived ?? detailJob.skipped_messages,
                    failed: detailJob.result?.failed ?? detailJob.failed_messages,
                  })}
                </Alert>

                {(detailJob.result?.skipped_samples?.length ||
                  (!detailJob.result && detailJob.skipped_messages > 0)) && (
                  <Stack spacing={0.5}>
                    <Typography variant="subtitle2">{t("bulk", "skippedTitle")}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t("bulk", "skippedHint")}
                    </Typography>
                    {(detailJob.result?.skipped_samples || []).map((s, i) => (
                      <Typography key={i} variant="body2" noWrap title={s.subject}>
                        • {s.subject || t("bulk", "noSubject")}
                      </Typography>
                    ))}
                    {!detailJob.result && (
                      <Typography variant="caption" color="text.secondary">
                        {t("bulk", "noSampleOldJob")}
                      </Typography>
                    )}
                  </Stack>
                )}

                {(detailJob.result?.archived_samples?.length || 0) > 0 && (
                  <Stack spacing={0.5}>
                    <Typography variant="subtitle2">{t("bulk", "archivedTitle")}</Typography>
                    {detailJob.result!.archived_samples!.map((s, i) => (
                      <Typography key={i} variant="body2" noWrap title={s.subject}>
                        • {s.subject || t("bulk", "noSubject")}
                      </Typography>
                    ))}
                  </Stack>
                )}

                {((detailJob.result?.failed_samples?.length || 0) > 0 ||
                  detailJob.error_message) && (
                  <Stack spacing={0.5}>
                    <Typography variant="subtitle2" color="error">
                      {t("bulk", "failedTitle")}
                    </Typography>
                    {detailJob.error_message && (
                      <Typography variant="body2" color="error">
                        {detailJob.error_message}
                      </Typography>
                    )}
                    {(detailJob.result?.failed_samples || []).map((s, i) => (
                      <Typography key={i} variant="body2" color="error">
                        • {s.subject || t("bulk", "noSubject")}
                        {s.error ? ` — ${s.error}` : ""}
                      </Typography>
                    ))}
                  </Stack>
                )}

                {detailJob.criteria && (
                  <Stack spacing={0.5}>
                    <Typography variant="subtitle2">{t("bulk", "criteriaTitle")}</Typography>
                    <Typography
                      component="pre"
                      variant="caption"
                      sx={{
                        m: 0,
                        p: 1,
                        bgcolor: "action.hover",
                        borderRadius: 1,
                        overflow: "auto",
                        maxHeight: 160,
                      }}
                    >
                      {JSON.stringify(detailJob.criteria, null, 2)}
                    </Typography>
                  </Stack>
                )}
              </Stack>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDetailJob(null)}>{t("common", "close")}</Button>
          </DialogActions>
        </Dialog>
      </PageShell>
    </AppLayout>
  );
}
