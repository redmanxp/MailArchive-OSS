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
import { useLocale } from "../i18n/LocaleContext";

type Props = {
  open: boolean;
  title?: string;
  message?: string;
  cancelling?: boolean;
  onCancel?: () => void;
  showCancel?: boolean;
};

/**
 * Blocking modal for long waits (simulation / prep).
 * Archive jobs continue in the background.
 */
export default function BulkPreparingModal({
  open,
  title,
  message,
  cancelling = false,
  onCancel,
  showCancel = true,
}: Props) {
  const { t } = useLocale();
  const resolvedTitle = title || t("bulkModal", "title");
  const resolvedMessage = message || t("bulkModal", "body");

  return (
    <Dialog
      open={open}
      fullWidth
      maxWidth="sm"
      disableEscapeKeyDown
      onClose={() => undefined}
      aria-labelledby="bulk-preparing-title"
    >
      <DialogTitle id="bulk-preparing-title">{resolvedTitle}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 0.5 }}>
          <Typography color="text.secondary">{resolvedMessage}</Typography>
          <LinearProgress />
          {cancelling && (
            <Typography variant="body2" color="text.secondary">
              {t("bulkModal", "cancelling")}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      {showCancel && onCancel && (
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button color="warning" variant="contained" onClick={onCancel} disabled={cancelling}>
            {cancelling ? t("bulkModal", "cancelling") : t("bulkModal", "cancel")}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
