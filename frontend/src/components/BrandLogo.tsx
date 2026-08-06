import { useEffect, useState } from "react";
import { Box } from "@mui/material";
import { brandingApiUrl, brandingFallbackUrl, type LogoKind } from "../utils/branding";

type Props = {
  kind: LogoKind;
  alt?: string;
  height?: number | string;
  maxWidth?: number | string;
  cacheBust?: number | string;
};

/** Prefers API branding (custom or default); falls back to static public assets. */
export default function BrandLogo({ kind, alt = "MailArchive", height, maxWidth, cacheBust }: Props) {
  const [src, setSrc] = useState(() => brandingApiUrl(kind, cacheBust));

  useEffect(() => {
    setSrc(brandingApiUrl(kind, cacheBust));
  }, [kind, cacheBust]);

  return (
    <Box
      component="img"
      src={src}
      alt={alt}
      onError={() => setSrc(brandingFallbackUrl(kind))}
      sx={{
        height: height ?? (kind === "icon" ? 40 : 120),
        maxWidth: maxWidth ?? (kind === "full" ? 280 : 48),
        width: "auto",
        objectFit: "contain",
        display: "block",
      }}
    />
  );
}
