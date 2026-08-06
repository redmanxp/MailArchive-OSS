/**
 * Fixed page header + optional filters; scrollable body; optional sticky footer (pagination).
 */
import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  filters?: ReactNode;
  alerts?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  /** When false, body grows naturally (forms without tables). Default true. */
  scrollBody?: boolean;
};

export default function PageShell({
  title,
  subtitle,
  actions,
  filters,
  alerts,
  footer,
  children,
  scrollBody = true,
}: Props) {
  return (
    <Box
      sx={{
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        width: "100%",
      }}
    >
      <Box
        sx={{
          flexShrink: 0,
          pb: 1,
          bgcolor: "background.default",
          zIndex: 30,
        }}
      >
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h5" component="h1">
              {title}
            </Typography>
            {subtitle ? (
              <Typography color="text.secondary" variant="body2" sx={{ mt: 0.25 }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          {actions ? <Box sx={{ flexShrink: 0 }}>{actions}</Box> : null}
        </Stack>
      </Box>

      {alerts ? <Box sx={{ flexShrink: 0, mb: 1 }}>{alerts}</Box> : null}

      {filters ? (
        <Box
          sx={{
            flexShrink: 0,
            mb: 1,
            position: "sticky",
            top: 0,
            zIndex: 25,
            bgcolor: "background.default",
          }}
        >
          {filters}
        </Box>
      ) : null}

      <Box
        sx={
          scrollBody
            ? {
                flex: 1,
                minHeight: 0,
                overflow: "auto",
              }
            : { flex: "0 0 auto" }
        }
      >
        {children}
      </Box>

      {footer ? (
        <Box
          sx={{
            flexShrink: 0,
            pt: 1,
            borderTop: "1px solid",
            borderColor: "divider",
            bgcolor: "background.default",
            zIndex: 20,
          }}
        >
          {footer}
        </Box>
      ) : null}
    </Box>
  );
}
