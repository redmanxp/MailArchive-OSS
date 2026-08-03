import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#0B3D5C" },
    secondary: { main: "#C45C26" },
    background: { default: "#F3F6F8", paper: "#FFFFFF" },
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
    h3: { fontFamily: '"IBM Plex Serif", Georgia, serif', fontWeight: 600 },
    h4: { fontFamily: '"IBM Plex Serif", Georgia, serif', fontWeight: 600 },
    h5: { fontFamily: '"IBM Plex Serif", Georgia, serif', fontWeight: 600 },
  },
  shape: { borderRadius: 10 },
});
