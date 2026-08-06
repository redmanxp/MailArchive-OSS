import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CssBaseline, ThemeProvider } from "@mui/material";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { LocaleProvider } from "./i18n/LocaleContext";
import { theme } from "./theme";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <LocaleProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </LocaleProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
