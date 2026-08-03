import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";

type Props = {
  open: boolean;
  title?: string;
  message?: string;
  cancelling?: boolean;
  onCancel?: () => void;
  /** Si false, solo muestra progreso sin botón cancelar */
  showCancel?: boolean;
};

/**
 * Modal bloqueante para esperas largas (simulación / preparación),
 * no para el job de archivado (ese sigue en segundo plano).
 */
export default function BulkPreparingModal({
  open,
  title = "Preparando archivado masivo",
  message = "Consultando correos en el proveedor. Esto puede demorar varios minutos.",
  cancelling = false,
  onCancel,
  showCancel = true,
}: Props) {
  return (
    <Dialog
      open={open}
      fullWidth
      maxWidth="sm"
      disableEscapeKeyDown
      onClose={() => undefined}
      aria-labelledby="bulk-preparing-title"
    >
      <DialogTitle id="bulk-preparing-title">{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 0.5 }}>
          <Typography color="text.secondary">{message}</Typography>
          <LinearProgress />
          {cancelling && (
            <Typography variant="body2" color="text.secondary">
              Cancelando…
            </Typography>
          )}
        </Stack>
      </DialogContent>
      {showCancel && onCancel && (
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button color="warning" variant="contained" onClick={onCancel} disabled={cancelling}>
            {cancelling ? "Cancelando…" : "Cancelar"}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
