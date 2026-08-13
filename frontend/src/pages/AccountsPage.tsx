import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  MenuItem,
  Pagination,
  Paper,
  Stack,
  Switch,
  Tab,
  Tabs,
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
import AddIcon from "@mui/icons-material/Add";
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import LinkOffIcon from "@mui/icons-material/LinkOff";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import ScheduleIcon from "@mui/icons-material/Schedule";
import SwapHorizIcon from "@mui/icons-material/SwapHoriz";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import ConfirmDialog from "../components/ConfirmDialog";
import { useAuth } from "../auth/AuthContext";
import {
  createImapAccount,
  deleteAccount,
  getAccountSchedule,
  hardDeleteAccount,
  listAccounts,
  listUsers,
  purgeAccountArchive,
  reconnectImapAccount,
  runAccountScheduleNow,
  startMicrosoftOAuth,
  testImapConnection,
  transferAccount,
  updateAccountSchedule,
  type AccountPublic,
  type ArchiveSchedule,
  type UserAdmin,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";
import { formatDateTime } from "../utils/datetime";

type LinkStep = "provider" | "imap";
type ProviderChoice = "microsoft365" | "imap" | "gmail" | "";
type TabKey = "active" | "unlinked";

const PAGE_SIZE = 25;
const PROVIDER_FILTERS = ["microsoft365", "imap", "gmail"] as const;
const GMAIL_IMAP = { host: "imap.gmail.com", port: 993, ssl: true } as const;

export default function AccountsPage() {
  const { t, tf } = useLocale();
  const { providerLabel, accountStatusLabel } = useLabels();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isStaff = user?.role === "admin" || user?.role === "supervisor";
  const isAdmin = user?.role === "admin";

  const [tab, setTab] = useState<TabKey>("active");
  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [filterQ, setFilterQ] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [infoSeverity, setInfoSeverity] = useState<"success" | "warning">("success");
  const [unlinkTarget, setUnlinkTarget] = useState<AccountPublic | null>(null);
  const [transferTarget, setTransferTarget] = useState<AccountPublic | null>(null);
  const [transferToUserId, setTransferToUserId] = useState<number | "">("");
  const [hardDeleteTarget, setHardDeleteTarget] = useState<AccountPublic | null>(null);
  const [purgeTarget, setPurgeTarget] = useState<AccountPublic | null>(null);
  const [purgeConfirm, setPurgeConfirm] = useState("");
  const [reconnectTarget, setReconnectTarget] = useState<AccountPublic | null>(null);
  const [scheduleTarget, setScheduleTarget] = useState<AccountPublic | null>(null);
  const [schedule, setSchedule] = useState<ArchiveSchedule | null>(null);
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedInterval, setSchedInterval] = useState(1440);
  const [schedLimit, setSchedLimit] = useState(500);
  const [schedAttachments, setSchedAttachments] = useState(false);
  const [schedHistorical, setSchedHistorical] = useState(false);
  const [loading, setLoading] = useState(false);

  const [linkOpen, setLinkOpen] = useState(false);
  const [linkStep, setLinkStep] = useState<LinkStep>("provider");
  const [provider, setProvider] = useState<ProviderChoice>("");

  const [host, setHost] = useState("mail.example.com");
  const [port, setPort] = useState(993);
  const [ssl, setSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const filteredAccounts = useMemo(() => {
    const q = filterQ.trim().toLowerCase();
    return accounts.filter((a) => {
      if (filterProvider === "gmail") {
        const host = (a.imap_host || "").toLowerCase();
        if (a.provider !== "gmail" && !host.includes("gmail.com")) return false;
      } else if (filterProvider && a.provider !== filterProvider) {
        return false;
      }
      if (!q) return true;
      const owner = `${a.owner_name || ""} ${a.owner_email || ""}`.toLowerCase();
      return (
        a.email.toLowerCase().includes(q) ||
        owner.includes(q) ||
        String(a.id).includes(q) ||
        String(a.user_id).includes(q)
      );
    });
  }, [accounts, filterQ, filterProvider]);

  const pageCount = Math.max(1, Math.ceil(filteredAccounts.length / PAGE_SIZE));
  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredAccounts.slice(start, start + PAGE_SIZE);
  }, [filteredAccounts, page]);

  useEffect(() => {
    const linked = params.get("linked");
    const email = params.get("email");
    const oauthError = params.get("error");
    if (linked === "1") {
      setInfoSeverity("success");
      setInfo(tf("accounts", "linkedMs", { email: email || "" }));
      setTab("active");
      navigate("/app/accounts", { replace: true });
    } else if (oauthError) {
      setError(tf("accounts", "oauthError", { error: oauthError }));
      navigate("/app/accounts", { replace: true });
    }
  }, [params, navigate, tf]);

  const refresh = useCallback(async () => {
    setAccounts(await listAccounts({ status: tab === "unlinked" ? "unlinked" : "active" }));
  }, [tab]);

  useEffect(() => {
    refresh().catch((err) => {
      setError(err?.response?.data?.detail || t("accounts", "loadError"));
    });
  }, [refresh, t]);

  useEffect(() => {
    setPage(1);
  }, [tab, filterQ, filterProvider]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  function openLinkModal() {
    setProvider("");
    setLinkStep("provider");
    setHost("mail.example.com");
    setPort(993);
    setSsl(true);
    setPassword("");
    setReconnectTarget(null);
    setError(null);
    setLinkOpen(true);
  }

  function closeLinkModal() {
    if (loading) return;
    setLinkOpen(false);
    setLinkStep("provider");
    setProvider("");
    setReconnectTarget(null);
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
              tf("accounts", "oauthError", { error: t("common", "error") })
          )
        );
        setLoading(false);
      }
      return;
    }
    if (provider === "gmail") {
      setHost(GMAIL_IMAP.host);
      setPort(GMAIL_IMAP.port);
      setSsl(GMAIL_IMAP.ssl);
      setLinkStep("imap");
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
      if (res.ok) {
        setInfoSeverity("success");
        setInfo(tf("accounts", "imapOk", { email: res.email || username }));
      } else {
        setInfoSeverity("warning");
        setInfo(`${t("common", "failedPrefix")}: ${res.detail}`);
      }
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

  async function onSaveImap(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (reconnectTarget) {
        const r = await reconnectImapAccount(reconnectTarget.id, {
          host,
          port,
          ssl,
          username,
          password,
        });
        setInfoSeverity(r.test_ok ? "success" : "warning");
        setInfo(
          r.test_ok
            ? tf("accounts", "reconnected", { email: r.email })
            : `${t("common", "failedPrefix")}: ${r.test_detail}`
        );
        setReconnectTarget(null);
        setTab("active");
      } else {
        await createImapAccount({ host, port, ssl, username, password });
        setInfoSeverity("success");
        setInfo(t("accounts", "imapSaved"));
      }
      setPassword("");
      setLinkOpen(false);
      setLinkStep("provider");
      await refresh();
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

  function openReconnect(account: AccountPublic) {
    setError(null);
    setReconnectTarget(account);
    if (account.provider === "microsoft365") {
      setLoading(true);
      startMicrosoftOAuth()
        .then(({ authorize_url }) => {
          window.location.href = authorize_url;
        })
        .catch((err: unknown) => {
          setError(
            String(
              (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                tf("accounts", "oauthError", { error: t("common", "error") })
            )
          );
          setLoading(false);
          setReconnectTarget(null);
        });
      return;
    }
    setHost(account.imap_host || "mail.example.com");
    setPort(account.imap_port || 993);
    setSsl(account.imap_ssl !== false);
    setUsername(account.imap_username || account.email);
    setPassword("");
    setProvider("imap");
    setLinkStep("imap");
    setLinkOpen(true);
  }

  async function confirmHardDelete() {
    if (!hardDeleteTarget) return;
    setLoading(true);
    setError(null);
    try {
      await hardDeleteAccount(hardDeleteTarget.id);
      setInfoSeverity("success");
      setInfo(tf("accounts", "hardDeleted", { email: hardDeleteTarget.email }));
      setHardDeleteTarget(null);
      await refresh();
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

  async function confirmPurge() {
    if (!purgeTarget) return;
    if (purgeConfirm.trim().toUpperCase() !== "ELIMINAR") {
      setError(t("accounts", "purgeConfirmHint"));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await purgeAccountArchive(purgeTarget.id, purgeConfirm.trim());
      setInfoSeverity(r.storage_errors > 0 ? "warning" : "success");
      setInfo(
        tf("accounts", "purged", {
          email: r.email,
          n: String(r.mails_deleted),
        })
      );
      setPurgeTarget(null);
      setPurgeConfirm("");
      await refresh();
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

  async function confirmUnlink() {
    if (unlinkTarget == null) return;
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await deleteAccount(unlinkTarget.id);
      setInfoSeverity("success");
      setInfo(t("accounts", "unlinked"));
      setUnlinkTarget(null);
      await refresh();
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

  async function openTransfer(account: AccountPublic) {
    setTransferTarget(account);
    setTransferToUserId("");
    setError(null);
    try {
      if (users.length === 0) {
        setUsers(await listUsers());
      }
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
    }
  }

  async function confirmTransfer() {
    if (transferTarget == null) return;
    if (transferToUserId === "") {
      setError(t("accounts", "transferTo"));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await transferAccount(transferTarget.id, Number(transferToUserId), true);
      setInfoSeverity("success");
      setInfo(tf("accounts", "transferred", { n: r.mails_reassigned }));
      setTransferTarget(null);
      await refresh();
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

  async function openSchedule(account: AccountPublic) {
    setScheduleTarget(account);
    setError(null);
    setLoading(true);
    try {
      const s = await getAccountSchedule(account.id);
      setSchedule(s);
      setSchedEnabled(s.enabled);
      setSchedInterval(s.interval_minutes || 1440);
      setSchedLimit(s.limit_per_run || 500);
      setSchedAttachments(Boolean(s.only_with_attachments));
      setSchedHistorical(Boolean(s.historical_backfill));
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
      setScheduleTarget(null);
    } finally {
      setLoading(false);
    }
  }

  async function saveSchedule() {
    if (!scheduleTarget) return;
    setLoading(true);
    setError(null);
    try {
      const s = await updateAccountSchedule(scheduleTarget.id, {
        enabled: schedEnabled,
        interval_minutes: schedInterval,
        limit_per_run: schedLimit,
        only_with_attachments: schedAttachments,
        historical_backfill: schedHistorical,
        folder_id: null,
        folder_path: null,
      });
      setSchedule(s);
      setInfoSeverity("success");
      setInfo(t("accounts", "scheduleSaved"));
      setScheduleTarget(null);
      await refresh();
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

  async function runScheduleNow() {
    if (!scheduleTarget || !schedEnabled) return;
    setLoading(true);
    setError(null);
    try {
      // Persist current form state first so run uses saved policy
      await updateAccountSchedule(scheduleTarget.id, {
        enabled: true,
        interval_minutes: schedInterval,
        limit_per_run: schedLimit,
        only_with_attachments: schedAttachments,
        historical_backfill: schedHistorical,
        folder_id: null,
        folder_path: null,
      });
      const s = await runAccountScheduleNow(scheduleTarget.id);
      setSchedule(s);
      setSchedEnabled(s.enabled);
      setInfoSeverity("success");
      setInfo(tf("accounts", "scheduleRunQueued", { id: String(s.job_id ?? s.last_job_id ?? "") }));
      await refresh();
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

  const transferCandidates = useMemo(
    () => users.filter((u) => u.status === "active" && u.id !== transferTarget?.user_id),
    [users, transferTarget]
  );

  return (
    <AppLayout>
      <PageShell
        title={isStaff ? t("accounts", "title") : t("accounts", "titleMine")}
        subtitle={isStaff ? t("accounts", "subtitleStaff") : t("accounts", "subtitleUser")}
        actions={
          tab === "active" ? (
            <Tooltip title={t("accounts", "linkTooltip")}>
              <IconButton
                color="primary"
                onClick={openLinkModal}
                aria-label={t("accounts", "linkTitle")}
                sx={{ border: "1px solid", borderColor: "divider" }}
              >
                <AddIcon />
              </IconButton>
            </Tooltip>
          ) : null
        }
        alerts={
          <>
            {error && (
              <Alert severity="error" onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            {info && (
              <Alert severity={infoSeverity} onClose={() => setInfo(null)} sx={{ mt: error ? 1 : 0 }}>
                {info}
              </Alert>
            )}
          </>
        }
        filters={
          <Paper
            elevation={0}
            sx={{
              p: 1.25,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
              <TextField
                size="small"
                label={t("accounts", "filterSearch")}
                value={filterQ}
                onChange={(e) => setFilterQ(e.target.value)}
                fullWidth
                placeholder={
                  isStaff
                    ? t("accounts", "filterSearchPlaceholderStaff")
                    : t("accounts", "filterSearchPlaceholder")
                }
              />
              <TextField
                select
                size="small"
                label={t("accounts", "filterProvider")}
                value={filterProvider}
                onChange={(e) => setFilterProvider(e.target.value)}
                sx={{ minWidth: 160 }}
              >
                <MenuItem value="">{t("accounts", "filterAllProviders")}</MenuItem>
                {PROVIDER_FILTERS.map((p) => (
                  <MenuItem key={p} value={p}>
                    {providerLabel(p)}
                  </MenuItem>
                ))}
              </TextField>
              <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                {tf("accounts", "filterCount", { n: filteredAccounts.length })}
              </Typography>
            </Stack>
          </Paper>
        }
        footer={
          filteredAccounts.length > PAGE_SIZE ? (
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
        <Tabs value={tab} onChange={(_, v: TabKey) => setTab(v)} sx={{ mb: 1.5, minHeight: 40 }}>
          <Tab value="active" label={t("accounts", "tabActive")} sx={{ minHeight: 40 }} />
          <Tab value="unlinked" label={t("accounts", "tabUnlinked")} sx={{ minHeight: 40 }} />
        </Tabs>
        <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>{t("accounts", "provider")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("accounts", "email")}</TableCell>
                  {isStaff && (
                    <TableCell sx={{ fontWeight: 600 }}>{t("accounts", "owner")}</TableCell>
                  )}
                  <TableCell sx={{ fontWeight: 600 }}>{t("accounts", "status")}</TableCell>
                  {tab === "unlinked" && (
                    <TableCell sx={{ fontWeight: 600 }}>{t("accounts", "archivedCount")}</TableCell>
                  )}
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {t("accounts", "actions")}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageItems.map((a) => (
                  <TableRow key={a.id} hover>
                    <TableCell>{providerLabel(a.provider)}</TableCell>
                    <TableCell>
                      {a.email}
                      {a.is_mine === false ? (
                        <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                          {t("accounts", "foreign")}
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
                    {tab === "unlinked" && (
                      <TableCell>{a.archived_count ?? "—"}</TableCell>
                    )}
                    <TableCell align="right">
                      <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                        {tab === "active" ? (
                          <>
                            {(a.is_mine !== false || isStaff) && (
                              <Tooltip
                                title={
                                  a.schedule_enabled
                                    ? t("accounts", "scheduleTooltipActive")
                                    : t("accounts", "scheduleTooltip")
                                }
                              >
                                <IconButton
                                  color={a.schedule_enabled ? "success" : "default"}
                                  onClick={() => openSchedule(a)}
                                  aria-label={t("accounts", "scheduleTooltip")}
                                  size="small"
                                >
                                  <ScheduleIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {isAdmin && (
                              <Tooltip title={t("accounts", "transferTooltip")}>
                                <IconButton
                                  color="primary"
                                  onClick={() => openTransfer(a)}
                                  aria-label={t("accounts", "transferTooltip")}
                                  size="small"
                                >
                                  <SwapHorizIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {(a.is_mine !== false || isStaff) && (
                              <Tooltip title={t("accounts", "unlinkTooltip")}>
                                <IconButton
                                  color="error"
                                  onClick={() => setUnlinkTarget(a)}
                                  aria-label={t("accounts", "unlinkTooltip")}
                                  size="small"
                                >
                                  <LinkOffIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </>
                        ) : (
                          <>
                            {(a.is_mine !== false || isStaff) && (
                              <Tooltip title={t("accounts", "reconnectTooltip")}>
                                <IconButton
                                  color="primary"
                                  onClick={() => openReconnect(a)}
                                  aria-label={t("accounts", "reconnectTooltip")}
                                  size="small"
                                >
                                  <RestartAltIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {isAdmin && (
                              <Tooltip title={t("accounts", "transferTooltip")}>
                                <IconButton
                                  color="primary"
                                  onClick={() => openTransfer(a)}
                                  aria-label={t("accounts", "transferTooltip")}
                                  size="small"
                                >
                                  <SwapHorizIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {(a.is_mine !== false || isAdmin) && (a.archived_count ?? 0) > 0 && (
                              <Tooltip title={t("accounts", "purgeTooltip")}>
                                <IconButton
                                  color="error"
                                  onClick={() => {
                                    setPurgeTarget(a);
                                    setPurgeConfirm("");
                                  }}
                                  aria-label={t("accounts", "purgeTooltip")}
                                  size="small"
                                >
                                  <DeleteSweepIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {(a.is_mine !== false || isAdmin) && (a.archived_count ?? 0) === 0 && (
                              <Tooltip title={t("accounts", "hardDeleteTooltip")}>
                                <IconButton
                                  color="error"
                                  onClick={() => setHardDeleteTarget(a)}
                                  aria-label={t("accounts", "hardDeleteTooltip")}
                                  size="small"
                                >
                                  <DeleteForeverIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
                {filteredAccounts.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={isStaff ? (tab === "unlinked" ? 6 : 5) : tab === "unlinked" ? 5 : 4}>
                      <Typography color="text.secondary" variant="body2">
                        {accounts.length === 0
                          ? tab === "unlinked"
                            ? t("accounts", "emptyUnlinked")
                            : t("accounts", "empty")
                          : t("accounts", "filterEmpty")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </PageShell>

      <Dialog open={linkOpen} onClose={closeLinkModal} fullWidth maxWidth="sm">
        <DialogTitle>
          {linkStep === "provider"
            ? t("accounts", "linkTitle")
            : reconnectTarget
              ? t("accounts", "reconnectImapTitle")
              : t("accounts", "imapTitle")}
        </DialogTitle>
        <DialogContent>
          {linkStep === "provider" && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Typography color="text.secondary" variant="body2">
                {t("accounts", "linkHint")}
              </Typography>
              <TextField
                select
                label={t("accounts", "chooseProvider")}
                value={provider}
                onChange={(e) => setProvider(e.target.value as ProviderChoice)}
                fullWidth
              >
                <MenuItem value="microsoft365">{providerLabel("microsoft365")}</MenuItem>
                <MenuItem value="gmail">{providerLabel("gmail")}</MenuItem>
                <MenuItem value="imap">{providerLabel("imap")}</MenuItem>
              </TextField>
            </Stack>
          )}
          {linkStep === "imap" && (
            <Stack spacing={2} component="form" id="imap-link-form" onSubmit={onSaveImap} sx={{ pt: 1 }}>
              {(provider === "gmail" || host === GMAIL_IMAP.host) && (
                <Alert severity="info">{t("accounts", "gmailAppPasswordHint")}</Alert>
              )}
              <TextField
                label={t("accounts", "host")}
                value={host}
                onChange={(e) => setHost(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("accounts", "port")}
                type="number"
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
                required
                fullWidth
              />
              <FormControlLabel
                control={<Switch checked={ssl} onChange={(e) => setSsl(e.target.checked)} />}
                label={t("accounts", "ssl")}
              />
              <TextField
                label={t("accounts", "username")}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("accounts", "password")}
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
                {t("common", "back")}
              </Button>
              <Button onClick={onTestImap} disabled={loading}>
                {t("accounts", "test")}
              </Button>
              <Button type="submit" form="imap-link-form" variant="contained" disabled={loading}>
                {t("common", "save")}
              </Button>
            </>
          )}
          {linkStep === "provider" && (
            <>
              <Button onClick={closeLinkModal} disabled={loading}>
                {t("common", "cancel")}
              </Button>
              <Button
                variant="contained"
                onClick={onContinueProvider}
                disabled={loading || !provider}
              >
                {t("common", "continue")}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      <Dialog
        open={scheduleTarget != null}
        onClose={() => !loading && setScheduleTarget(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("accounts", "scheduleTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {tf("accounts", "scheduleHint", { email: scheduleTarget?.email || "" })}
            </Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={schedEnabled}
                  onChange={(e) => setSchedEnabled(e.target.checked)}
                  disabled={loading}
                />
              }
              label={t("accounts", "scheduleEnabled")}
            />
            <TextField
              select
              label={t("accounts", "scheduleInterval")}
              value={schedInterval}
              onChange={(e) => setSchedInterval(Number(e.target.value))}
              disabled={loading}
              size="small"
            >
              <MenuItem value={60}>{t("accounts", "interval1h")}</MenuItem>
              <MenuItem value={360}>{t("accounts", "interval6h")}</MenuItem>
              <MenuItem value={1440}>{t("accounts", "interval1d")}</MenuItem>
              <MenuItem value={10080}>{t("accounts", "interval7d")}</MenuItem>
            </TextField>
            <TextField
              type="number"
              label={t("accounts", "scheduleLimit")}
              value={schedLimit}
              onChange={(e) => setSchedLimit(Number(e.target.value) || 500)}
              disabled={loading}
              size="small"
              inputProps={{ min: 1, max: 2000 }}
              helperText={t("accounts", "scheduleLimitHint")}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={schedAttachments}
                  onChange={(e) => setSchedAttachments(e.target.checked)}
                  disabled={loading}
                />
              }
              label={t("accounts", "scheduleAttachments")}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={schedHistorical}
                  onChange={(e) => setSchedHistorical(e.target.checked)}
                  disabled={loading}
                />
              }
              label={t("accounts", "scheduleHistorical")}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5, display: "block" }}>
              {t("accounts", "scheduleHistoricalHint")}
            </Typography>
            {schedule && (
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">
                  {t("accounts", "scheduleStatus")}: {schedule.last_status || "—"}
                  {schedule.last_error ? ` · ${schedule.last_error}` : ""}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t("accounts", "scheduleLastRun")}:{" "}
                  {schedule.last_run_at ? formatDateTime(schedule.last_run_at) : t("common", "emptyDash")}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t("accounts", "scheduleNextRun")}:{" "}
                  {schedule.next_run_at ? formatDateTime(schedule.next_run_at) : t("common", "emptyDash")}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t("accounts", "scheduleWatermark")}:{" "}
                  {schedule.watermark_at ? formatDateTime(schedule.watermark_at) : t("common", "emptyDash")}
                </Typography>
                {schedHistorical && (
                  <Typography variant="caption" color="text.secondary">
                    {t("accounts", "scheduleBackfill")}:{" "}
                    {schedule.backfill_watermark_at
                      ? formatDateTime(schedule.backfill_watermark_at)
                      : t("common", "emptyDash")}
                  </Typography>
                )}
              </Stack>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setScheduleTarget(null)} disabled={loading}>
            {t("common", "cancel")}
          </Button>
          <Button
            onClick={runScheduleNow}
            disabled={loading || !schedEnabled}
            color="secondary"
          >
            {t("accounts", "scheduleRunNow")}
          </Button>
          <Button variant="contained" onClick={saveSchedule} disabled={loading}>
            {t("common", "save")}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={unlinkTarget != null}
        title={t("accounts", "unlinkTitle")}
        message={tf("accounts", "unlinkMessage", { email: unlinkTarget?.email || "" })}
        confirmLabel={t("accounts", "unlinkConfirm")}
        confirmColor="error"
        loading={loading}
        onCancel={() => !loading && setUnlinkTarget(null)}
        onConfirm={confirmUnlink}
      />

      <ConfirmDialog
        open={transferTarget != null}
        title={t("accounts", "transferTitle")}
        message={tf("accounts", "transferMessage", { email: transferTarget?.email || "" })}
        confirmLabel={t("accounts", "transferConfirm")}
        confirmColor="primary"
        loading={loading}
        onCancel={() => !loading && setTransferTarget(null)}
        onConfirm={confirmTransfer}
      >
        <TextField
          select
          fullWidth
          size="small"
          sx={{ mt: 2 }}
          label={t("accounts", "transferTo")}
          value={transferToUserId}
          onChange={(e) => setTransferToUserId(e.target.value === "" ? "" : Number(e.target.value))}
          disabled={loading}
        >
          {transferCandidates.map((u) => (
            <MenuItem key={u.id} value={u.id}>
              {u.name} ({u.email})
            </MenuItem>
          ))}
        </TextField>
      </ConfirmDialog>

      <ConfirmDialog
        open={hardDeleteTarget != null}
        title={t("accounts", "hardDeleteTitle")}
        message={tf("accounts", "hardDeleteMessage", { email: hardDeleteTarget?.email || "" })}
        confirmLabel={t("accounts", "hardDeleteConfirm")}
        confirmColor="error"
        loading={loading}
        onCancel={() => !loading && setHardDeleteTarget(null)}
        onConfirm={confirmHardDelete}
      />

      <ConfirmDialog
        open={purgeTarget != null}
        title={t("accounts", "purgeTitle")}
        message={tf("accounts", "purgeMessage", {
          email: purgeTarget?.email || "",
          n: String(purgeTarget?.archived_count ?? 0),
        })}
        confirmLabel={t("accounts", "purgeConfirm")}
        confirmColor="error"
        loading={loading}
        onCancel={() => {
          if (loading) return;
          setPurgeTarget(null);
          setPurgeConfirm("");
        }}
        onConfirm={confirmPurge}
      >
        <TextField
          fullWidth
          size="small"
          sx={{ mt: 2 }}
          label={t("accounts", "purgeConfirmLabel")}
          value={purgeConfirm}
          onChange={(e) => setPurgeConfirm(e.target.value)}
          helperText={t("accounts", "purgeConfirmHint")}
          disabled={loading}
          autoComplete="off"
        />
      </ConfirmDialog>
    </AppLayout>
  );
}
