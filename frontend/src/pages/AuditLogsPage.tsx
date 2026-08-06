import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  IconButton,
  Pagination,
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
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import SearchIcon from "@mui/icons-material/Search";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import ConfirmDialog from "../components/ConfirmDialog";
import { clearAuditLogs, listAuditLogs, type AuditLogItem } from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { formatDateTime } from "../utils/datetime";

const PAGE_SIZE = 25;

export default function AuditLogsPage() {
  const { t, tf } = useLocale();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [clearOpen, setClearOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function load(nextPage = page, query = q) {
    setLoading(true);
    setError(null);
    try {
      const r = await listAuditLogs({
        q: query.trim() || undefined,
        limit: PAGE_SIZE,
        offset: (nextPage - 1) * PAGE_SIZE,
      });
      setItems(r.items);
      setTotal(r.total);
      setPage(nextPage);
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("audit", "loadError")
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
    await load(1);
  }

  async function onClear() {
    setBusy(true);
    setError(null);
    try {
      const r = await clearAuditLogs();
      setInfo(r.message);
      setClearOpen(false);
      await load(1, "");
      setQ("");
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("audit", "clearError")
        )
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout>
      <PageShell
        title={t("audit", "title")}
        subtitle={t("audit", "subtitle")}
        actions={
          <Tooltip title={t("audit", "clearTooltip")}>
            <span>
              <IconButton color="error" onClick={() => setClearOpen(true)} disabled={total === 0 || busy}>
                <DeleteSweepIcon />
              </IconButton>
            </span>
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
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                size="small"
                label={t("audit", "search")}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                fullWidth
                placeholder={t("audit", "searchPlaceholder")}
              />
              <Button type="submit" variant="contained" size="small" startIcon={<SearchIcon />} disabled={loading}>
                {t("audit", "search")}
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                {tf("audit", "count", { n: total })}
              </Typography>
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
                  <TableCell sx={{ fontWeight: 600, width: 64 }}>{t("audit", "id")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("audit", "action")}</TableCell>
                  <TableCell sx={{ fontWeight: 600, width: 88 }}>{t("audit", "user")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("audit", "resource")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("audit", "detail")}</TableCell>
                  <TableCell sx={{ fontWeight: 600, width: 140 }}>{t("audit", "date")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((l) => (
                  <TableRow key={l.id} hover>
                    <TableCell>#{l.id}</TableCell>
                    <TableCell>
                      <Typography variant="body2">{l.action}</Typography>
                    </TableCell>
                    <TableCell>{l.user_id ?? t("common", "emptyDash")}</TableCell>
                    <TableCell>
                      <Typography variant="caption" display="block">
                        {l.resource_type || t("common", "emptyDash")}
                        {l.resource_id ? ` · ${l.resource_id}` : ""}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ maxWidth: 280 }}>
                      <Typography variant="caption" noWrap title={l.details ? JSON.stringify(l.details) : ""}>
                        {l.details ? JSON.stringify(l.details) : t("common", "emptyDash")}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">{formatDateTime(l.created_at)}</Typography>
                    </TableCell>
                  </TableRow>
                ))}
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography color="text.secondary" variant="body2">
                        {t("audit", "empty")}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </PageShell>

      <ConfirmDialog
        open={clearOpen}
        title={t("audit", "clearTitle")}
        message={t("audit", "clearMessage")}
        confirmLabel={t("audit", "clearConfirm")}
        confirmColor="error"
        loading={busy}
        onCancel={() => !busy && setClearOpen(false)}
        onConfirm={onClear}
      />
    </AppLayout>
  );
}
