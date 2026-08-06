/**
 * Employee departure wizard — archive mailbox (optional) + transfer/unlink + deactivate.
 */
import { FormEvent, useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import {
  getDeparturePreview,
  listUsers,
  runEmployeeDeparture,
  type DeparturePreview,
  type UserAdmin,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";

export default function DeparturePage() {
  const { t, tf } = useLocale();
  const { providerLabel } = useLabels();
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams();
  const userId = Number(id);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DeparturePreview | null>(null);
  const [activeUsers, setActiveUsers] = useState<UserAdmin[]>([]);

  const [archiveEnabled, setArchiveEnabled] = useState(true);
  const [olderThanDays, setOlderThanDays] = useState("");
  const [archiveLimit, setArchiveLimit] = useState("500");
  const [accountsAction, setAccountsAction] = useState<"unlink" | "transfer">("transfer");
  const [transferTo, setTransferTo] = useState<number | "">("");
  const [disableSchedules, setDisableSchedules] = useState(true);
  const [doneSummary, setDoneSummary] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(userId)) {
      setError(t("users", "notFound"));
      setLoading(false);
      return;
    }
    Promise.all([getDeparturePreview(userId), listUsers()])
      .then(([p, users]) => {
        setPreview(p);
        setActiveUsers(users.filter((u) => u.status === "active" && u.id !== userId));
        if (me?.id) setTransferTo(me.id);
      })
      .catch((e) =>
        setError(String(e?.response?.data?.detail || t("departure", "loadError")))
      )
      .finally(() => setLoading(false));
  }, [userId, me?.id, t]);

  useEffect(() => {
    if (archiveEnabled) {
      setAccountsAction("transfer");
      if (transferTo === "" && me?.id) setTransferTo(me.id);
    }
  }, [archiveEnabled, me?.id, transferTo]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!preview) return;
    setError(null);
    if (accountsAction === "transfer" && transferTo === "") {
      setError(t("users", "deactivateTransferTo"));
      return;
    }
    setSubmitting(true);
    try {
      const days = olderThanDays.trim() ? Number(olderThanDays) : null;
      const result = await runEmployeeDeparture(userId, {
        accounts_action: accountsAction,
        transfer_to_user_id: accountsAction === "transfer" ? Number(transferTo) : undefined,
        archive_enabled: archiveEnabled,
        older_than_days: days && days >= 1 ? days : null,
        archive_limit: Math.max(1, Math.min(Number(archiveLimit) || 500, 2000)),
        disable_schedules: disableSchedules,
      });
      const jobs = result.job_ids.length
        ? tf("departure", "jobsStarted", { n: result.job_ids.length })
        : t("departure", "noJobs");
      const skipped = result.archive_skipped.length
        ? ` ${tf("departure", "skipped", { n: result.archive_skipped.length })}`
        : "";
      setDoneSummary(
        tf("departure", "success", {
          email: result.email,
          accounts: result.accounts_touched,
          jobs,
        }) + skipped
      );
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (doneSummary) {
    return (
      <AppLayout>
        <PageShell title={t("departure", "title")} subtitle={t("departure", "subtitle")}>
          <Alert severity="success" sx={{ mb: 2 }}>
            {doneSummary}
          </Alert>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" component={RouterLink} to="/app/bulk">
              {t("departure", "goJobs")}
            </Button>
            <Button variant="outlined" component={RouterLink} to="/app/users">
              {t("departure", "backUsers")}
            </Button>
          </Stack>
        </PageShell>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <PageShell
        title={t("departure", "title")}
        subtitle={
          preview
            ? tf("departure", "forUser", {
                name: preview.user.name,
                email: preview.user.email,
              })
            : t("departure", "subtitle")
        }
        alerts={
          error ? (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          ) : null
        }
      >
        {loading || !preview ? (
          <Typography color="text.secondary">{t("common", "loading")}</Typography>
        ) : (
          <Paper
            component="form"
            onSubmit={onSubmit}
            elevation={0}
            sx={{ p: 2, border: "1px solid", borderColor: "divider", maxWidth: 720 }}
          >
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {t("departure", "accountsHeading")}
            </Typography>
            {preview.accounts.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t("departure", "noAccounts")}
              </Typography>
            ) : (
              <Table size="small" sx={{ mb: 2 }}>
                <TableHead>
                  <TableRow>
                    <TableCell>{t("accounts", "email")}</TableCell>
                    <TableCell>{t("accounts", "provider")}</TableCell>
                    <TableCell>{t("accounts", "status")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.accounts.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell>{a.email}</TableCell>
                      <TableCell>{providerLabel(a.provider)}</TableCell>
                      <TableCell>{a.status}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            <Stack spacing={2}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={archiveEnabled}
                    onChange={(e) => setArchiveEnabled(e.target.checked)}
                    disabled={preview.accounts.length === 0}
                  />
                }
                label={t("departure", "archiveEnabled")}
              />
              {archiveEnabled && preview.accounts.length > 0 && (
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                  <TextField
                    label={t("departure", "olderThanDays")}
                    type="text"
                    inputMode="numeric"
                    value={olderThanDays}
                    onChange={(e) => setOlderThanDays(e.target.value.replace(/\D/g, ""))}
                    helperText={t("departure", "olderThanDaysHint")}
                    fullWidth
                  />
                  <TextField
                    label={t("departure", "archiveLimit")}
                    type="text"
                    inputMode="numeric"
                    value={archiveLimit}
                    onChange={(e) => setArchiveLimit(e.target.value.replace(/\D/g, ""))}
                    onBlur={() => {
                      if (!archiveLimit || Number(archiveLimit) < 1) setArchiveLimit("500");
                      else if (Number(archiveLimit) > 2000) setArchiveLimit("2000");
                    }}
                    helperText={t("departure", "archiveLimitHint")}
                    fullWidth
                  />
                </Stack>
              )}

              <FormControlLabel
                control={
                  <Checkbox
                    checked={disableSchedules}
                    onChange={(e) => setDisableSchedules(e.target.checked)}
                    disabled={preview.accounts.length === 0}
                  />
                }
                label={t("departure", "disableSchedules")}
              />

              <Typography variant="subtitle2">{t("departure", "accountsAction")}</Typography>
              <Alert severity="info" sx={{ py: 0.5 }}>
                {archiveEnabled
                  ? t("departure", "transferRequiredHint")
                  : t("departure", "unlinkOkHint")}
              </Alert>
              <RadioGroup
                value={accountsAction}
                onChange={(e) => setAccountsAction(e.target.value as "unlink" | "transfer")}
              >
                <FormControlLabel
                  value="transfer"
                  control={<Radio size="small" />}
                  label={t("users", "deactivateTransfer")}
                />
                <FormControlLabel
                  value="unlink"
                  control={<Radio size="small" />}
                  label={t("users", "deactivateUnlink")}
                  disabled={archiveEnabled && preview.accounts.length > 0}
                />
              </RadioGroup>
              {accountsAction === "transfer" && (
                <TextField
                  select
                  fullWidth
                  size="small"
                  label={t("users", "deactivateTransferTo")}
                  value={transferTo}
                  onChange={(e) =>
                    setTransferTo(e.target.value === "" ? "" : Number(e.target.value))
                  }
                >
                  {activeUsers.map((u) => (
                    <MenuItem key={u.id} value={u.id}>
                      {u.name} ({u.email})
                    </MenuItem>
                  ))}
                </TextField>
              )}

              <Alert severity="warning">{t("departure", "warning")}</Alert>

              <Stack direction="row" spacing={1} justifyContent="flex-end">
                <Button onClick={() => navigate("/app/users")} disabled={submitting}>
                  {t("common", "cancel")}
                </Button>
                <Button type="submit" variant="contained" color="error" disabled={submitting}>
                  {submitting ? t("departure", "running") : t("departure", "confirm")}
                </Button>
              </Stack>
            </Stack>
          </Paper>
        )}
      </PageShell>
    </AppLayout>
  );
}
