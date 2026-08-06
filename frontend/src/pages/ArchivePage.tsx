import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArchiveIcon from "@mui/icons-material/Archive";
import SearchIcon from "@mui/icons-material/Search";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import {
  archiveMessage,
  listAccountFolders,
  listAccountMessages,
  listAccounts,
  type AccountPublic,
  type FolderPublic,
  type ProviderMessage,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";
import { formatDateTime } from "../utils/datetime";
import { folderDepth, folderLeafName } from "../utils/folders";
import { providerLabel } from "../utils/labels";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ArchivePage() {
  const { t } = useLocale();
  const [accounts, setAccounts] = useState<AccountPublic[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [folders, setFolders] = useState<FolderPublic[]>([]);
  const [folderId, setFolderId] = useState("");
  const [messages, setMessages] = useState<ProviderMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<ProviderMessage | null>(null);
  const [deleteAfter, setDeleteAfter] = useState(false);

  useEffect(() => {
    listAccounts()
      .then((rows) => {
        setAccounts(rows);
        if (rows.length === 1) setAccountId(rows[0].id);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("archive", "loadAccountsError"))));
  }, [t]);

  useEffect(() => {
    if (!accountId) {
      setFolders([]);
      setFolderId("");
      setMessages([]);
      return;
    }
    setLoading(true);
    listAccountFolders(Number(accountId))
      .then((rows) => {
        setFolders(rows);
        const inbox =
          rows.find((f) => /inbox|bandeja/i.test(f.name)) ||
          rows.find((f) => f.path === "INBOX") ||
          rows[0];
        setFolderId(inbox?.id || "");
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("archive", "loadFoldersError"))))
      .finally(() => setLoading(false));
  }, [accountId, t]);

  async function loadMessages(e?: FormEvent) {
    e?.preventDefault();
    if (!accountId) return;
    setError(null);
    setLoading(true);
    try {
      const rows = await listAccountMessages(Number(accountId), {
        folder_id: folderId || undefined,
        limit: 50,
      });
      setMessages(rows);
      if (rows.length === 0) setInfo(t("archive", "noMessages"));
      else setInfo(null);
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

  async function confirmArchive() {
    if (!pending || !accountId) return;
    setLoading(true);
    setError(null);
    try {
      const folderMeta = folders.find((f) => f.id === folderId);
      await archiveMessage({
        account_id: Number(accountId),
        message_id: pending.id,
        folder_id: folderId || pending.folder || undefined,
        folder_path: folderMeta?.path || folderMeta?.name || undefined,
        delete_after_archive: deleteAfter,
      });
      setInfo(deleteAfter ? t("archive", "doneDeleted") : t("archive", "doneKept"));
      setPending(null);
      setDeleteAfter(false);
      await loadMessages();
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("archive", "archiveError")
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const noSubject = t("archive", "noSubject");

  return (
    <AppLayout>
      <PageShell
        title={t("archive", "title")}
        subtitle={t("archive", "subtitle")}
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
            sx={{ p: 2, border: "1px solid", borderColor: "divider" }}
            elevation={0}
            component="form"
            onSubmit={loadMessages}
          >
            <Stack spacing={2} direction={{ xs: "column", md: "row" }} alignItems={{ md: "center" }}>
              <TextField
                select
                size="small"
                label={t("archive", "account")}
                value={accountId}
                onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
                fullWidth
                required
              >
                {accounts.map((a) => (
                  <MenuItem key={a.id} value={a.id}>
                    {a.email} ({providerLabel(a.provider)})
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label={t("archive", "folder")}
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                fullWidth
                disabled={!folders.length}
                SelectProps={{
                  renderValue: (selected) => {
                    const f = folders.find((x) => x.id === selected);
                    if (!f) return "";
                    const label = f.path || f.name;
                    return `${folderLeafName(label, f.name)}${f.total_items != null ? ` (${f.total_items})` : ""}`;
                  },
                }}
              >
                {folders.map((f) => {
                  const label = f.path || f.name;
                  const depth = folderDepth(label);
                  return (
                    <MenuItem key={f.id} value={f.id} sx={{ pl: 2 + depth * 2.5 }}>
                      {folderLeafName(label, f.name)}
                      {f.total_items != null ? ` (${f.total_items})` : ""}
                    </MenuItem>
                  );
                })}
              </TextField>
              <Tooltip title={loading ? t("archive", "listing") : t("archive", "list")}>
                <span>
                  <IconButton
                    type="submit"
                    color="primary"
                    disabled={!accountId || loading}
                    aria-label={t("archive", "list")}
                  >
                    <SearchIcon />
                  </IconButton>
                </span>
              </Tooltip>
            </Stack>
          </Paper>
        }
      >
        <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 1 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>{t("archive", "subject")}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t("archive", "from")}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t("archive", "date")}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t("archive", "size")}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t("archive", "attachments")}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  {t("archive", "action")}
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {messages.map((m) => (
                <TableRow key={m.id} hover>
                  <TableCell>{m.subject || noSubject}</TableCell>
                  <TableCell>{m.from_address}</TableCell>
                  <TableCell>{formatDateTime(m.received_at || m.sent_at)}</TableCell>
                  <TableCell>{formatBytes(m.size_bytes)}</TableCell>
                  <TableCell>{m.has_attachments ? t("common", "yes") : t("common", "no")}</TableCell>
                  <TableCell align="right">
                    <Tooltip title={t("archive", "title")}>
                      <IconButton
                        size="small"
                        color="primary"
                        aria-label={t("archive", "title")}
                        onClick={() => {
                          setPending(m);
                          setDeleteAfter(false);
                        }}
                      >
                        <ArchiveIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {messages.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography color="text.secondary">{t("archive", "empty")}</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </PageShell>

      <Dialog open={!!pending} onClose={() => setPending(null)}>
        <DialogTitle>{t("archive", "confirmTitle")}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            {t("archive", "confirmBody")}{" "}
            <strong>{pending?.subject || noSubject}</strong>
          </DialogContentText>
          <FormControlLabel
            control={
              <Checkbox
                checked={deleteAfter}
                onChange={(e) => setDeleteAfter(e.target.checked)}
                color="warning"
              />
            }
            label={t("archive", "alsoDelete")}
          />
          {deleteAfter && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {t("archive", "deleteWarning")}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPending(null)}>{t("common", "cancel")}</Button>
          <Button
            variant="contained"
            color={deleteAfter ? "warning" : "primary"}
            onClick={confirmArchive}
            disabled={loading}
          >
            {deleteAfter ? t("archive", "archiveDelete") : t("archive", "archiveKeep")}
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
}
