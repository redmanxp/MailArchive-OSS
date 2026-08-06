import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
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
import LinkOffIcon from "@mui/icons-material/LinkOff";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
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
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";

type LinkStep = "provider" | "imap";
type ProviderChoice = "microsoft365" | "imap" | "";

const PAGE_SIZE = 25;

export default function AccountsPage() {
  const { t, tf } = useLocale();
  const { providerLabel, accountStatusLabel } = useLabels();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isStaff = user?.role === "admin" || user?.role === "supervisor";

  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [unlinkTarget, setUnlinkTarget] = useState<AccountPublic | null>(null);
  const [loading, setLoading] = useState(false);

  const [linkOpen, setLinkOpen] = useState(false);
  const [linkStep, setLinkStep] = useState<LinkStep>("provider");
  const [provider, setProvider] = useState<ProviderChoice>("");

  const [host, setHost] = useState("mail.example.com");
  const [port, setPort] = useState(993);
  const [ssl, setSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const pageCount = Math.max(1, Math.ceil(accounts.length / PAGE_SIZE));
  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return accounts.slice(start, start + PAGE_SIZE);
  }, [accounts, page]);

  useEffect(() => {
    const linked = params.get("linked");
    const email = params.get("email");
    const oauthError = params.get("error");
    if (linked === "1") {
      setInfo(tf("accounts", "linkedMs", { email: email || "" }));
      navigate("/app/accounts", { replace: true });
    } else if (oauthError) {
      setError(tf("accounts", "oauthError", { error: oauthError }));
      navigate("/app/accounts", { replace: true });
    }
  }, [params, navigate, tf]);

  async function refresh() {
    setAccounts(await listAccounts());
  }

  useEffect(() => {
    refresh().catch((err) => {
      setError(err?.response?.data?.detail || t("accounts", "loadError"));
    });
  }, [t]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

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
              tf("accounts", "oauthError", { error: t("common", "error") })
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
      setInfo(
        res.ok
          ? tf("accounts", "imapOk", { email: res.email || username })
          : `${t("common", "failedPrefix")}: ${res.detail}`
      );
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
      await createImapAccount({ host, port, ssl, username, password });
      setInfo(t("accounts", "imapSaved"));
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

  async function confirmUnlink() {
    if (unlinkTarget == null) return;
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await deleteAccount(unlinkTarget.id);
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

  return (
    <AppLayout>
      <PageShell
        title={isStaff ? t("accounts", "title") : t("accounts", "titleMine")}
        subtitle={isStaff ? t("accounts", "subtitleStaff") : t("accounts", "subtitleUser")}
        actions={
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
          accounts.length > PAGE_SIZE ? (
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
                    <TableCell align="right">
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
                    </TableCell>
                  </TableRow>
                ))}
                {accounts.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={isStaff ? 5 : 4}>
                      <Typography color="text.secondary" variant="body2">
                        {t("accounts", "empty")}
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
          {linkStep === "provider" ? t("accounts", "linkTitle") : t("accounts", "imapTitle")}
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
                <MenuItem value="imap">{providerLabel("imap")}</MenuItem>
              </TextField>
            </Stack>
          )}
          {linkStep === "imap" && (
            <Stack spacing={2} component="form" id="imap-link-form" onSubmit={onSaveImap} sx={{ pt: 1 }}>
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
    </AppLayout>
  );
}
