/**
 * Users list — sticky header with + to open create form; same form for edit.
 */
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Alert,
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
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import LockResetIcon from "@mui/icons-material/LockReset";
import PersonOffIcon from "@mui/icons-material/PersonOff";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import ConfirmDialog from "../components/ConfirmDialog";
import { deactivateUser, listUsers, resetUserPassword, type UserAdmin } from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";

const PAGE_SIZE = 25;

export default function UsersPage() {
  const { t, tf } = useLocale();
  const { roleLabel, userStatusLabel } = useLabels();
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [resetTarget, setResetTarget] = useState<UserAdmin | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<UserAdmin | null>(null);

  const pageCount = Math.max(1, Math.ceil(users.length / PAGE_SIZE));
  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return users.slice(start, start + PAGE_SIZE);
  }, [users, page]);

  async function refresh() {
    setUsers(await listUsers());
  }

  useEffect(() => {
    refresh().catch((e) =>
      setError(String(e?.response?.data?.detail || t("users", "loadError")))
    );
  }, [t]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  return (
    <AppLayout>
      <PageShell
        title={t("users", "title")}
        subtitle={t("users", "subtitle")}
        actions={
          <Tooltip title={t("users", "addTooltip")}>
            <IconButton
              color="primary"
              component={RouterLink}
              to="/app/users/new"
              aria-label={t("users", "addTooltip")}
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
          users.length > PAGE_SIZE ? (
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
                  <TableCell sx={{ fontWeight: 600 }}>{t("users", "id")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("users", "name")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("users", "email")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("users", "role")}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t("users", "status")}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {t("users", "actions")}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageItems.map((u) => (
                  <TableRow key={u.id} hover>
                    <TableCell>{u.id}</TableCell>
                    <TableCell>{u.name}</TableCell>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>{roleLabel(u.role)}</TableCell>
                    <TableCell>{userStatusLabel(u.status)}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t("users", "edit")}>
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/app/users/${u.id}`)}
                          aria-label={t("users", "edit")}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("users", "reset")}>
                        <IconButton
                          size="small"
                          onClick={() => setResetTarget(u)}
                          aria-label={t("users", "reset")}
                        >
                          <LockResetIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("users", "deactivate")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setDeactivateTarget(u)}
                          aria-label={t("users", "deactivate")}
                        >
                          <PersonOffIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {users.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography color="text.secondary" variant="body2">
                        {t("users", "empty")}
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
        open={!!resetTarget}
        title={t("users", "resetTitle")}
        message={tf("users", "resetMessage", { email: resetTarget?.email || "" })}
        confirmLabel={t("users", "resetConfirm")}
        onCancel={() => setResetTarget(null)}
        onConfirm={async () => {
          if (!resetTarget) return;
          try {
            const r = await resetUserPassword(resetTarget.id, true);
            setInfo(
              r.email_sent
                ? tf("users", "resetSent", { email: resetTarget.email })
                : tf("users", "resetFail", { detail: r.email_detail || "" })
            );
            setResetTarget(null);
          } catch (err: unknown) {
            setError(
              String(
                (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  t("common", "error")
              )
            );
          }
        }}
      />

      <ConfirmDialog
        open={!!deactivateTarget}
        title={t("users", "deactivateTitle")}
        message={tf("users", "deactivateMessage", { email: deactivateTarget?.email || "" })}
        confirmLabel={t("users", "deactivateConfirm")}
        confirmColor="error"
        onCancel={() => setDeactivateTarget(null)}
        onConfirm={async () => {
          if (!deactivateTarget) return;
          try {
            await deactivateUser(deactivateTarget.id);
            setDeactivateTarget(null);
            setInfo(tf("users", "deactivated", { email: deactivateTarget.email }));
            await refresh();
          } catch (err: unknown) {
            setError(
              String(
                (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  t("common", "error")
              )
            );
          }
        }}
      />
    </AppLayout>
  );
}
