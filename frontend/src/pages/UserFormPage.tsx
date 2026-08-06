/**
 * Create / edit user — same screen for both routes.
 */
import { FormEvent, useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Button,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import { createUser, listUsers, updateUser, type UserAdmin } from "../api/client";
import { useLocale } from "../i18n/LocaleContext";

const ROLE_VALUES = ["admin", "supervisor", "user", "readonly"] as const;
const STATUS_VALUES = ["active", "inactive"] as const;

export default function UserFormPage() {
  const { t, tf } = useLocale();
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = !id || id === "new";

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("user");
  const [status, setStatus] = useState<string>("active");
  const [sendEmail, setSendEmail] = useState(true);
  const [existing, setExisting] = useState<UserAdmin | null>(null);

  useEffect(() => {
    if (isNew) {
      setLoading(false);
      return;
    }
    const userId = Number(id);
    if (!Number.isFinite(userId)) {
      setError(t("users", "notFound"));
      setLoading(false);
      return;
    }
    listUsers()
      .then((list) => {
        const u = list.find((x) => x.id === userId);
        if (!u) {
          setError(t("users", "notFound"));
          return;
        }
        setExisting(u);
        setName(u.name);
        setEmail(u.email);
        setRole(u.role);
        setStatus(u.status);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("users", "loadError"))))
      .finally(() => setLoading(false));
  }, [id, isNew, t]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setSaving(true);
    try {
      if (isNew) {
        const r = await createUser({
          name: name.trim(),
          email: email.trim(),
          role,
          send_welcome_email: sendEmail,
        });
        setInfo(
          r.email_sent
            ? tf("users", "createdSent", { email: r.email })
            : tf("users", "createdNoEmail", {
                email: r.email,
                detail: r.email_detail || t("users", "smtpFallback"),
              })
        );
        setTimeout(() => navigate("/app/users"), 900);
      } else if (existing) {
        await updateUser(existing.id, {
          name: name.trim(),
          role,
          status,
        });
        setInfo(tf("users", "updated", { email: existing.email }));
        setTimeout(() => navigate("/app/users"), 700);
      }
    } catch (err: unknown) {
      setError(
        String(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            t("common", "error")
        )
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppLayout>
      <PageShell
        title={isNew ? t("users", "createTitle") : t("users", "editTitle")}
        subtitle={existing?.email || undefined}
        scrollBody={false}
        actions={
          <Button component={RouterLink} to="/app/users" size="small">
            {t("common", "back")}
          </Button>
        }
        alerts={
          <>
            {error && <Alert severity="error">{error}</Alert>}
            {info && (
              <Alert severity="success" sx={{ mt: error ? 1 : 0 }}>
                {info}
              </Alert>
            )}
          </>
        }
      >
        {loading ? (
          <Typography>{t("common", "loading")}</Typography>
        ) : (
          <Paper
            component="form"
            onSubmit={onSubmit}
            elevation={0}
            sx={{ p: 3, maxWidth: 560, border: "1px solid", borderColor: "divider" }}
          >
            <Stack spacing={2}>
              <TextField
                label={t("users", "name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t("users", "email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                fullWidth
                disabled={!isNew}
              />
              <TextField
                select
                label={t("users", "role")}
                value={role}
                onChange={(e) => setRole(e.target.value)}
                fullWidth
              >
                {ROLE_VALUES.map((r) => (
                  <MenuItem key={r} value={r}>
                    {t("roles", r)}
                  </MenuItem>
                ))}
              </TextField>
              {!isNew && (
                <TextField
                  select
                  label={t("users", "status")}
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  fullWidth
                >
                  {STATUS_VALUES.map((s) => (
                    <MenuItem key={s} value={s}>
                      {t("userStatus", s)}
                    </MenuItem>
                  ))}
                </TextField>
              )}
              {isNew && (
                <FormControlLabel
                  control={
                    <Switch checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />
                  }
                  label={t("users", "sendEmail")}
                />
              )}
              <Stack direction="row" spacing={2}>
                <Button type="submit" variant="contained" disabled={saving || name.trim().length < 2}>
                  {saving
                    ? t("common", "saving")
                    : isNew
                      ? t("users", "submitCreate")
                      : t("users", "submitEdit")}
                </Button>
                <Button component={RouterLink} to="/app/users" disabled={saving}>
                  {t("common", "cancel")}
                </Button>
              </Stack>
            </Stack>
          </Paper>
        )}
      </PageShell>
    </AppLayout>
  );
}
