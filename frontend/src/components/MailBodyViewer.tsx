import { useMemo } from "react";
import { Box, Paper, Typography } from "@mui/material";
import { useLocale } from "../i18n/LocaleContext";

type Props = {
  text?: string | null;
  html?: string | null;
  isHtml?: boolean;
  minHeight?: number | string;
  maxHeight?: number | string;
};

function wrapHtmlDocument(html: string): string {
  const cleaned = html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/\son\w+\s*=\s*(['"]).*?\1/gi, "");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"/><base target="_blank"/><style>
    body{margin:12px;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;color:#1a1a1a;word-wrap:break-word;}
    img{max-width:100%;height:auto;}
    table{max-width:100%;}
    a{color:#0B3D5C;}
  </style></head><body>${cleaned}</body></html>`;
}

export default function MailBodyViewer({
  text,
  html,
  isHtml,
  minHeight = 360,
  maxHeight = "60vh",
}: Props) {
  const { t } = useLocale();
  const showHtml = Boolean(isHtml && html) || Boolean(html && html.length > 40);
  const srcDoc = useMemo(() => (showHtml && html ? wrapHtmlDocument(html) : ""), [showHtml, html]);

  if (showHtml && srcDoc) {
    return (
      <Paper
        variant="outlined"
        sx={{
          overflow: "hidden",
          bgcolor: "#fff",
          minHeight,
          maxHeight,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Box sx={{ px: 1.5, py: 0.75, borderBottom: "1px solid", borderColor: "divider", bgcolor: "grey.50" }}>
          <Typography variant="caption" color="text.secondary">
            {t("mailBody", "htmlView")}
          </Typography>
        </Box>
        <Box
          component="iframe"
          title={t("mailBody", "iframeTitle")}
          sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
          srcDoc={srcDoc}
          sx={{
            border: 0,
            width: "100%",
            flex: 1,
            minHeight,
            bgcolor: "#fff",
          }}
        />
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        minHeight: typeof minHeight === "number" ? Math.min(minHeight, 280) : minHeight,
        maxHeight,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        fontFamily: "IBM Plex Sans, Segoe UI, sans-serif",
        fontSize: 14,
        lineHeight: 1.5,
      }}
    >
      {text || t("mailBody", "noText")}
    </Paper>
  );
}
