import { Link as RouterLink, useLocation } from "react-router-dom";
import {
  Box,
  Button,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import { useAuth } from "../auth/AuthContext";

import { roleLabel } from "../utils/labels";

const DRAWER_WIDTH = 232;

const NAV = [
  { to: "/app", label: "Panel", end: true },
  { to: "/app/accounts", label: "Cuentas" },
  { to: "/app/archive", label: "Archivar" },
  { to: "/app/bulk", label: "Masivo" },
  { to: "/app/mails", label: "Archivados" },
  { to: "/app/users", label: "Usuarios", admin: true },
  { to: "/app/audit", label: "Auditoría", admin: true },
  { to: "/app/settings", label: "Configuración", admin: true },
];

function isActive(pathname: string, to: string, end?: boolean) {
  if (end) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isAdmin = user?.role === "admin";
  const roleText = roleLabel(user?.role);

  return (
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
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 0.2 }}>
            MailArchive
          </Typography>
        </Box>
        <Divider sx={{ borderColor: "rgba(255,255,255,0.16)" }} />

        <List sx={{ flex: 1, py: 1, px: 1, overflowY: "auto" }}>
          {NAV.filter((n) => !n.admin || isAdmin).map((item) => {
            const active = isActive(location.pathname, item.to, item.end);
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
                  primary={item.label}
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
            title="Ver perfil"
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
            Salir
          </Button>
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          minHeight: "100vh",
          px: { xs: 2, md: 3 },
          py: { xs: 2, md: 3 },
          overflowX: "auto",
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
