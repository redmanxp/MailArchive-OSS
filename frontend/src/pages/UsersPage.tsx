/**
 * Users list — tabs Activos / Desactivados; restore or hard-delete from deactivated.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Alert,
  FormControlLabel,
  IconButton,
  MenuItem,
  Pagination,
  Paper,
  Radio,
  RadioGroup,
  Stack,
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
import EditIcon from "@mui/icons-material/Edit";
import LockResetIcon from "@mui/icons-material/LockReset";
import PersonOffIcon from "@mui/icons-material/PersonOff";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import WorkOffIcon from "@mui/icons-material/WorkOff";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import ConfirmDialog from "../components/ConfirmDialog";
import {
  deactivateUser,
  hardDeleteUser,
  listUsers,
  resetUserPassword,
  restoreUser,
  type UserAdmin,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { useLabels } from "../utils/labels";

const PAGE_SIZE = 25;
const ROLE_FILTERS = ["admin", "supervisor", "user", "readonly"] as const;

type TabKey = "active" | "deactivated";

export default function UsersPage() {
  const { t, tf } = useLocale();
  const { roleLabel, userStatusLabel } = useLabels();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("active");
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [activeUsers, setActiveUsers] = useState<UserAdmin[]>([]);
  const [filterQ, setFilterQ] = useState("");
  const [filterRole, setFilterRole] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [infoSeverity, setInfoSeverity] = useState<"success" | "warning">("success");
  const [setupUrl, setSetupUrl] = useState<string | null>(null);
  const [resetTarget, setResetTarget] = useState<UserAdmin | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<UserAdmin | null>(null);
  const [deactivateAction, setDeactivateAction] = useState<"unlink" | "transfer">("unlink");
  const [deactivateTransferTo, setDeactivateTransferTo] = useState<number | "">("");
  const [restoreTarget, setRestoreTarget] = useState<UserAdmin | null>(null);
  const [hardDeleteTarget, setHardDeleteTarget] = useState<UserAdmin | null>(null);
  const [hardDeleteReassignTo, setHardDeleteReassignTo] = useState<number | "">("");

  const filteredUsers = useMemo(() => {
    const q = filterQ.trim().toLowerCase();
    return users.filter((u) => {
      if (filterRole && u.role !== filterRole) return false;
      if (!q) return true;
      return (
        u.name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        String(u.id).includes(q)
      );
    });
  }, [users, filterQ, filterRole]);

  const pageCount = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredUsers.slice(start, start + PAGE_SIZE);
  }, [filteredUsers, page]);

  const refresh = useCallback(async () => {
    const [active, deactivated] = await Promise.all([
      listUsers(),
      listUsers({ deleted: true }),
    ]);
    setActiveUsers(active);
    setUsers(tab === "deactivated" ? deactivated : active);
  }, [tab]);

  useEffect(() => {
    refresh().catch((e) =>
      setError(String(e?.response?.data?.detail || t("users", "loadError")))
    );
  }, [refresh, t]);

  useEffect(() => {
    setPage(1);
  }, [tab, filterQ, filterRole]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  return (
    <AppLayout>
      <PageShell
        title={t("users", "title")}
        subtitle={t("users", "subtitle")}
        actions={
          tab === "active" ? (
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
              <Alert
                severity={infoSeverity}
                onClose={() => {
                  setInfo(null);
                  setSetupUrl(null);
                }}
                sx={{ mt: error ? 1 : 0 }}
              >
                {info}
              </Alert>
            )}
            {setupUrl && (
              <TextField
                label={t("users", "setupUrl")}
                value={setupUrl}
                fullWidth
                size="small"
                sx={{ mt: 1 }}
                InputProps={{ readOnly: true }}
                helperText={t("users", "setupUrlHint")}
                onFocus={(e) => e.target.select()}
              />
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
                label={t("users", "filterSearch")}
                value={filterQ}
                onChange={(e) => setFilterQ(e.target.value)}
                fullWidth
                placeholder={t("users", "filterSearchPlaceholder")}
              />
              <TextField
                select
                size="small"
                label={t("users", "filterRole")}
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
                sx={{ minWidth: 160 }}
              >
                <MenuItem value="">{t("users", "filterAllRoles")}</MenuItem>
                {ROLE_FILTERS.map((r) => (
                  <MenuItem key={r} value={r}>
                    {roleLabel(r)}
                  </MenuItem>
                ))}
              </TextField>
              <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                {tf("users", "filterCount", { n: filteredUsers.length })}
              </Typography>
            </Stack>
          </Paper>
        }
        footer={
          filteredUsers.length > PAGE_SIZE ? (
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
        <Tabs
          value={tab}
          onChange={(_, v: TabKey) => setTab(v)}
          sx={{ mb: 1.5, minHeight: 40 }}
        >
          <Tab value="active" label={t("users", "tabActive")} sx={{ minHeight: 40 }} />
          <Tab value="deactivated" label={t("users", "tabDeactivated")} sx={{ minHeight: 40 }} />
        </Tabs>
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
                      {tab === "active" ? (
                        <>
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
                          <Tooltip title={t("users", "departure")}>
                            <IconButton
                              size="small"
                              color="warning"
                              onClick={() => navigate(`/app/users/${u.id}/departure`)}
                              aria-label={t("users", "departure")}
                            >
                              <WorkOffIcon fontSize="small" />
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
                        </>
                      ) : (
                        <>
                          <Tooltip title={t("users", "restore")}>
                            <IconButton
                              size="small"
                              color="primary"
                              onClick={() => setRestoreTarget(u)}
                              aria-label={t("users", "restore")}
                            >
                              <RestartAltIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("users", "hardDelete")}>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => {
                                setHardDeleteTarget(u);
                                setHardDeleteReassignTo("");
                              }}
                              aria-label={t("users", "hardDelete")}
                            >
                              <DeleteForeverIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {filteredUsers.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography color="text.secondary" variant="body2">
                        {users.length === 0
                          ? tab === "deactivated"
                            ? t("users", "emptyDeactivated")
                            : t("users", "empty")
                          : t("users", "filterEmpty")}
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
            if (r.email_sent) {
              setInfoSeverity("success");
              setInfo(tf("users", "resetSent", { email: resetTarget.email }));
              setSetupUrl(null);
            } else {
              setInfoSeverity("warning");
              setInfo(tf("users", "resetFail", { detail: r.email_detail || "" }));
              setSetupUrl(r.setup_url || null);
            }
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
        onCancel={() => {
          setDeactivateTarget(null);
          setDeactivateAction("unlink");
          setDeactivateTransferTo("");
        }}
        onConfirm={async () => {
          if (!deactivateTarget) return;
          if (deactivateAction === "transfer" && deactivateTransferTo === "") {
            setError(t("users", "deactivateTransferTo"));
            return;
          }
          try {
            await deactivateUser(deactivateTarget.id, {
              accounts_action: deactivateAction,
              transfer_to_user_id:
                deactivateAction === "transfer" ? Number(deactivateTransferTo) : undefined,
            });
            setDeactivateTarget(null);
            setDeactivateAction("unlink");
            setDeactivateTransferTo("");
            setInfoSeverity("success");
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
      >
        <RadioGroup
          sx={{ mt: 1.5 }}
          value={deactivateAction}
          onChange={(e) => setDeactivateAction(e.target.value as "unlink" | "transfer")}
        >
          <FormControlLabel
            value="unlink"
            control={<Radio size="small" />}
            label={t("users", "deactivateUnlink")}
          />
          <FormControlLabel
            value="transfer"
            control={<Radio size="small" />}
            label={t("users", "deactivateTransfer")}
          />
        </RadioGroup>
        {deactivateAction === "transfer" && (
          <TextField
            select
            fullWidth
            size="small"
            sx={{ mt: 1 }}
            label={t("users", "deactivateTransferTo")}
            value={deactivateTransferTo}
            onChange={(e) =>
              setDeactivateTransferTo(e.target.value === "" ? "" : Number(e.target.value))
            }
          >
            {activeUsers
              .filter((u) => u.status === "active" && u.id !== deactivateTarget?.id)
              .map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </MenuItem>
              ))}
          </TextField>
        )}
      </ConfirmDialog>

      <ConfirmDialog
        open={!!restoreTarget}
        title={t("users", "restoreTitle")}
        message={tf("users", "restoreMessage", { email: restoreTarget?.email || "" })}
        confirmLabel={t("users", "restoreConfirm")}
        onCancel={() => setRestoreTarget(null)}
        onConfirm={async () => {
          if (!restoreTarget) return;
          try {
            await restoreUser(restoreTarget.id);
            setInfoSeverity("success");
            setInfo(tf("users", "restored", { email: restoreTarget.email }));
            setRestoreTarget(null);
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

      <ConfirmDialog
        open={!!hardDeleteTarget}
        title={t("users", "hardDeleteTitle")}
        message={tf("users", "hardDeleteMessage", { email: hardDeleteTarget?.email || "" })}
        confirmLabel={t("users", "hardDeleteConfirm")}
        confirmColor="error"
        onCancel={() => {
          setHardDeleteTarget(null);
          setHardDeleteReassignTo("");
        }}
        onConfirm={async () => {
          if (!hardDeleteTarget) return;
          try {
            await hardDeleteUser(
              hardDeleteTarget.id,
              hardDeleteReassignTo === "" ? undefined : Number(hardDeleteReassignTo)
            );
            setInfoSeverity("success");
            setInfo(tf("users", "hardDeleted", { email: hardDeleteTarget.email }));
            setHardDeleteTarget(null);
            setHardDeleteReassignTo("");
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
      >
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          {t("users", "hardDeleteArchiveHint")}
        </Typography>
        <TextField
          select
          fullWidth
          size="small"
          sx={{ mt: 1.5 }}
          label={t("users", "hardDeleteReassignTo")}
          value={hardDeleteReassignTo}
          helperText={t("users", "hardDeleteReassignHint")}
          onChange={(e) =>
            setHardDeleteReassignTo(e.target.value === "" ? "" : Number(e.target.value))
          }
        >
          <MenuItem value="">
            <em>{t("users", "hardDeleteReassignNone")}</em>
          </MenuItem>
          {activeUsers
            .filter((u) => u.status === "active")
            .map((u) => (
              <MenuItem key={u.id} value={u.id}>
                {u.name} ({u.email})
              </MenuItem>
            ))}
        </TextField>
      </ConfirmDialog>
    </AppLayout>
  );
}
