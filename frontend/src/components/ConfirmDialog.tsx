import type { ReactNode } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from "@mui/material";
import { useLocale } from "../i18n/LocaleContext";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmColor?: "primary" | "warning" | "error";
  loading?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  confirmColor = "primary",
  loading = false,
  children,
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useLocale();
  const confirm = confirmLabel || t("common", "confirm");
  const cancel = cancelLabel || t("common", "cancel");

  return (
    <Dialog open={open} onClose={loading ? undefined : onCancel} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
        {children}
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={loading}>
          {cancel}
        </Button>
        <Button variant="contained" color={confirmColor} onClick={onConfirm} disabled={loading}>
          {loading ? t("common", "processing") : confirm}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
