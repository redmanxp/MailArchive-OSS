import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import { getDashboardMetrics, type DashboardMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";
import { formatDateTime } from "../utils/datetime";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function MetricCard({
  label,
  value,
  href,
  tone,
}: {
  label: string;
  value: string | number;
  href?: string;
  tone?: "error" | "warning";
}) {
  const border =
    tone === "error" ? "error.main" : tone === "warning" ? "warning.main" : "divider";
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        flex: "1 1 140px",
        minWidth: 140,
        border: "1px solid",
        borderColor: border,
        textDecoration: "none",
        color: "inherit",
        display: "block",
      }}
      component={href ? RouterLink : "div"}
      {...(href ? { to: href } : {})}
    >
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={600} sx={{ mt: 0.5 }}>
        {value}
      </Typography>
    </Paper>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLocale();
  const { roleLabel } = useLabels();
  const isAdmin = user?.role === "admin";
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardMetrics()
      .then(setMetrics)
      .catch(() => setMetricsError(t("dashboard", "metricsError")));
  }, [t]);

  return (
    <AppLayout>
      <PageShell title={t("dashboard", "title")} scrollBody={false}>
        <Stack spacing={2}>
          {metricsError && <Alert severity="warning">{metricsError}</Alert>}

          {metrics && (
            <Paper sx={{ p: 3 }} elevation={0}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
                <Typography variant="h6">{t("dashboard", "metrics")}</Typography>
                <Chip
                  size="small"
                  label={metrics.scope === "tenant" ? t("dashboard", "scopeTenant") : t("dashboard", "scopeOwn")}
                  variant="outlined"
                />
              </Stack>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5 }}>
                {metrics.users_count != null && (
                  <MetricCard label={t("dashboard", "metricUsers")} value={metrics.users_count} />
                )}
                <MetricCard label={t("dashboard", "metricAccounts")} value={metrics.accounts_count} />
                <MetricCard label={t("dashboard", "metricMails")} value={metrics.mails_count} />
                <MetricCard label={t("dashboard", "metricStorage")} value={formatBytes(metrics.storage_bytes)} />
                <MetricCard label={t("dashboard", "metricAttachments")} value={metrics.attachments_count} />
                <MetricCard
                  label={t("dashboard", "metricJobs")}
                  value={metrics.jobs_active}
                  href="/app/jobs"
                />
              </Box>

              <Typography variant="subtitle2" sx={{ mt: 2.5, mb: 1 }}>
                {t("dashboard", "archiveHealth")}
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5 }}>
                <MetricCard
                  label={t("dashboard", "metricJobsFailed")}
                  value={metrics.jobs_failed ?? 0}
                  href="/app/jobs"
                  tone={(metrics.jobs_failed ?? 0) > 0 ? "error" : undefined}
                />
                <MetricCard
                  label={t("dashboard", "metricSchedulesErrors")}
                  value={metrics.schedules_with_errors ?? 0}
                  href="/app/accounts"
                  tone={(metrics.schedules_with_errors ?? 0) > 0 ? "warning" : undefined}
                />
                <MetricCard
                  label={t("dashboard", "metricLastArchive")}
                  value={
                    metrics.last_archive_at
                      ? formatDateTime(metrics.last_archive_at)
                      : t("common", "emptyDash")
                  }
                />
              </Box>

              {metrics.health && (
                <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" sx={{ width: "100%", mb: 0.5 }}>
                    {t("dashboard", "metricHealth")}
                  </Typography>
                  <Chip
                    size="small"
                    color={metrics.health.db_ok ? "success" : "error"}
                    label={metrics.health.db_ok ? t("dashboard", "healthDbOk") : t("dashboard", "healthDbFail")}
                  />
                  <Chip
                    size="small"
                    color={metrics.health.storage_ok ? "success" : "error"}
                    label={
                      metrics.health.storage_ok
                        ? t("dashboard", "healthStorageOk")
                        : t("dashboard", "healthStorageFail")
                    }
                  />
                </Stack>
              )}
            </Paper>
          )}

          <Paper sx={{ p: 3 }} elevation={0}>
            <Typography variant="h6">{t("dashboard", "session")}</Typography>
            <Typography>
              {t("dashboard", "email")}: {user?.email}
            </Typography>
            <Typography>
              {t("dashboard", "role")}: {roleLabel(user?.role)}
            </Typography>
          </Paper>

          <Paper sx={{ p: 3 }} elevation={0}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard", "mail")}
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <Button component={RouterLink} to="/app/archive" variant="contained">
                {t("dashboard", "archive")}
              </Button>
              <Button component={RouterLink} to="/app/bulk" variant="outlined">
                {t("dashboard", "bulk")}
              </Button>
              <Button component={RouterLink} to="/app/mails" variant="outlined">
                {t("dashboard", "mails")}
              </Button>
              <Button component={RouterLink} to="/app/accounts" variant="outlined">
                {t("dashboard", "accounts")}
              </Button>
            </Stack>
          </Paper>

          {isAdmin && (
            <Paper sx={{ p: 3 }} elevation={0}>
              <Typography variant="h6" gutterBottom>
                {t("dashboard", "admin")}
              </Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <Button component={RouterLink} to="/app/users" variant="contained">
                  {t("dashboard", "users")}
                </Button>
                <Button component={RouterLink} to="/app/settings" variant="outlined">
                  {t("dashboard", "settings")}
                </Button>
                <Button component={RouterLink} to="/app/audit" variant="outlined">
                  {t("dashboard", "audit")}
                </Button>
              </Stack>
            </Paper>
          )}

          {!isAdmin && <Alert severity="info">{t("dashboard", "welcome")}</Alert>}
        </Stack>
      </PageShell>
    </AppLayout>
  );
}
