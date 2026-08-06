import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import {
  Box,
  Button,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  ThemeProvider,
  Typography,
} from "@mui/material";
import { createTheme } from "@mui/material/styles";
import { getAppearance } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import BrandLogo from "../components/BrandLogo";
import { useLocale } from "../i18n/LocaleContext";
import { theme as baseTheme } from "../theme";
import { useLabels } from "../utils/labels";

const DRAWER_WIDTH = 232;

const NAV = [
  { to: "/app", key: "dashboard", end: true },
  { to: "/app/accounts", key: "accounts" },
  { to: "/app/archive", key: "archive" },
  { to: "/app/bulk", key: "bulk" },
  { to: "/app/mails", key: "mails" },
  { to: "/app/users", key: "users", admin: true },
  { to: "/app/audit", key: "audit", admin: true },
  { to: "/app/settings", key: "settings", admin: true },
] as const;

function isActive(pathname: string, to: string, end?: boolean) {
  if (end) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const { roleLabel } = useLabels();
  const location = useLocation();
  const isAdmin = user?.role === "admin";
  const roleText = roleLabel(user?.role);
  const [brandName, setBrandName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [logoBust, setLogoBust] = useState(0);

  useEffect(() => {
    getAppearance()
      .then((a) => {
        setBrandName(a.brand_name || "");
        setPrimaryColor(a.primary_color || "");
        setLogoBust(Date.now());
      })
      .catch(() => undefined);
  }, [location.pathname]);

  const themed = useMemo(() => {
    if (!primaryColor) return baseTheme;
    return createTheme({
      ...baseTheme,
      palette: {
        ...baseTheme.palette,
        primary: { main: primaryColor },
      },
    });
  }, [primaryColor]);

  const title = brandName || t("common", "appName", "MailArchive");

  const body = (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            borderRight: "1px solid",
            borderColor: "divider",
            bgcolor: "primary.main",
            color: "primary.contrastText",
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        <Box sx={{ px: 2.5, py: 2.25 }}>
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Box
              sx={{
                bgcolor: "#fff",
                borderRadius: 1.5,
                p: 0.5,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <BrandLogo kind="icon" height={32} maxWidth={32} cacheBust={logoBust} alt={title} />
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 0.2, lineHeight: 1.2 }} noWrap title={title}>
              {title}
            </Typography>
          </Stack>
        </Box>
        <Divider sx={{ borderColor: "rgba(255,255,255,0.16)" }} />

        <List sx={{ flex: 1, py: 1, px: 1, overflowY: "auto" }}>
          {NAV.filter((n) => !("admin" in n && n.admin) || isAdmin).map((item) => {
            const active = isActive(location.pathname, item.to, "end" in item ? item.end : false);
            return (
              <ListItemButton
                key={item.to}
                component={RouterLink}
                to={item.to}
                selected={active}
                sx={{
                  borderRadius: 1,
                  mb: 0.25,
                  color: "inherit",
                  opacity: active ? 1 : 0.82,
                  "&.Mui-selected": {
                    bgcolor: "rgba(255,255,255,0.16)",
                    "&:hover": { bgcolor: "rgba(255,255,255,0.22)" },
                  },
                  "&:hover": { bgcolor: "rgba(255,255,255,0.1)" },
                }}
              >
                <ListItemText
                  primary={t("nav", item.key)}
                  primaryTypographyProps={{
                    fontWeight: active ? 600 : 400,
                    fontSize: "0.9375rem",
                  }}
                />
              </ListItemButton>
            );
          })}
        </List>

        <Box sx={{ mt: "auto", px: 2, py: 2, borderTop: "1px solid rgba(255,255,255,0.16)" }}>
          <Box
            component={RouterLink}
            to="/app/profile"
            title={t("nav", "profile")}
            sx={{
              display: "block",
              color: "inherit",
              textDecoration: "none",
              borderRadius: 1,
              px: 0.5,
              py: 0.5,
              mx: -0.5,
              "&:hover": { bgcolor: "rgba(255,255,255,0.1)" },
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap title={user?.name}>
              {user?.name || "—"}
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.85, display: "block" }} noWrap>
              {roleText}
            </Typography>
            {user?.email && (
              <Typography variant="caption" sx={{ opacity: 0.7, display: "block", mt: 0.25 }} noWrap title={user.email}>
                {user.email}
              </Typography>
            )}
          </Box>
          <Button
            color="inherit"
            size="small"
            onClick={() => logout()}
            sx={{ mt: 1.25, px: 0, minWidth: 0, opacity: 0.9, textTransform: "none" }}
          >
            {t("common", "logout")}
          </Button>
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          height: "100vh",
          maxHeight: "100vh",
          px: { xs: 2, md: 3 },
          py: { xs: 2, md: 2.5 },
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {children}
      </Box>
    </Box>
  );

  if (!primaryColor) return body;
  return <ThemeProvider theme={themed}>{body}</ThemeProvider>;
}
