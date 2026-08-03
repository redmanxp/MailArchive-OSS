import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Box,
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
import ConfirmDialog from "../components/ConfirmDialog";
import { clearAuditLogs, listAuditLogs, type AuditLogItem } from "../api/client";
import { formatDateTime } from "../utils/datetime";

const PAGE_SIZE = 25;

export default function AuditLogsPage() {
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
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al cargar")
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
        String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "No se pudo borrar")
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
        <Box>
          <Typography variant="h5">Registros de auditoría</Typography>
          <Typography color="text.secondary" variant="body2">
            Solo administradores. Buscá por acción, recurso o detalle.
          </Typography>
        </Box>
        <Tooltip title="Borrar todos los registros">
          <span>
            <IconButton color="error" onClick={() => setClearOpen(true)} disabled={total === 0 || busy}>
              <DeleteSweepIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {info && (
        <Alert severity="success" sx={{ mb: 1 }} onClose={() => setInfo(null)}>
          {info}
        </Alert>
      )}

      <Paper
        component="form"
        onSubmit={onSearch}
        elevation={0}
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          p: 1.25,
          mb: 1,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            size="small"
            label="Buscar"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            fullWidth
            placeholder="acción, recurso, detalle…"
          />
          <Button type="submit" variant="contained" size="small" startIcon={<SearchIcon />} disabled={loading}>
            Buscar
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
            {total} registro{total === 1 ? "" : "s"}
          </Typography>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
        <TableContainer sx={{ maxHeight: "calc(100vh - 260px)" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, width: 64 }}>ID</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Acción</TableCell>
                <TableCell sx={{ fontWeight: 600, width: 88 }}>Usuario</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Recurso</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Detalle</TableCell>
                <TableCell sx={{ fontWeight: 600, width: 140 }}>Fecha</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((l) => (
                <TableRow key={l.id} hover>
                  <TableCell>#{l.id}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{l.action}</Typography>
                  </TableCell>
                  <TableCell>{l.user_id ?? "—"}</TableCell>
                  <TableCell>
                    <Typography variant="caption" display="block">
                      {l.resource_type || "—"}
                      {l.resource_id ? ` · ${l.resource_id}` : ""}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ maxWidth: 280 }}>
                    <Typography variant="caption" noWrap title={l.details ? JSON.stringify(l.details) : ""}>
                      {l.details ? JSON.stringify(l.details) : "—"}
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
                      Sin registros.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {total > PAGE_SIZE && (
          <Stack direction="row" justifyContent="center" sx={{ py: 1 }}>
            <Pagination
              size="small"
              count={pageCount}
              page={page}
              onChange={(_, p) => load(p)}
              disabled={loading}
              color="primary"
            />
          </Stack>
        )}
      </Paper>

      <ConfirmDialog
        open={clearOpen}
        title="Borrar auditoría"
        message="Se borrarán TODOS los registros de auditoría de este tenant. Quedará un único registro indicando el borrado. ¿Continuar?"
        confirmLabel="Borrar todo"
        confirmColor="error"
        loading={busy}
        onCancel={() => !busy && setClearOpen(false)}
        onConfirm={onClear}
      />
    </AppLayout>
  );
}
