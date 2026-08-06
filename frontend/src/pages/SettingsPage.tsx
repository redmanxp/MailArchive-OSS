/**
 * Admin settings: SMTP · Templates · Language · Data & storage · Appearance.
 */
import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import AppLayout from "../layouts/AppLayout";
import PageShell from "../components/PageShell";
import {
  getSmtpSettings,
  getSystemSettings,
  setTenantLocale,
  testSmtpSettings,
  updateSmtpSettings,
  type EmailTemplateBlock,
  type EmailTemplates,
  type SmtpSettings,
  type SystemSettings,
} from "../api/client";
import { useLocale } from "../i18n/LocaleContext";

const emptyBlock = (): EmailTemplateBlock => ({
  subject: "",
  greeting: "",
  intro: "",
  button_label: "",
  footer: "",
  link_fallback: "",
});

function TemplateFields({
  title,
  block,
  onChange,
  labels,
}: {
  title: string;
  block: EmailTemplateBlock;
  onChange: (next: EmailTemplateBlock) => void;
  labels: {
    subject: string;
    greeting: string;
    intro: string;
    buttonLabel: string;
    footer: string;
    linkFallback: string;
  };
}) {
  return (
    <Stack spacing={2}>
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
      <TextField label={labels.subject} value={block.subject} onChange={(e) => onChange({ ...block, subject: e.target.value })} fullWidth />
      <TextField label={labels.greeting} value={block.greeting} onChange={(e) => onChange({ ...block, greeting: e.target.value })} fullWidth />
      <TextField label={labels.intro} value={block.intro} onChange={(e) => onChange({ ...block, intro: e.target.value })} fullWidth multiline minRows={3} />
      <TextField label={labels.buttonLabel} value={block.button_label} onChange={(e) => onChange({ ...block, button_label: e.target.value })} fullWidth />
      <TextField label={labels.footer} value={block.footer} onChange={(e) => onChange({ ...block, footer: e.target.value })} fullWidth multiline minRows={2} />
      <TextField label={labels.linkFallback} value={block.link_fallback} onChange={(e) => onChange({ ...block, link_fallback: e.target.value })} fullWidth />
    </Stack>
  );
}

export default function SettingsPage() {
  const { t, setLocale, locales, locale } = useLocale();
  const [tab, setTab] = useState(0);
  const [settings, setSettings] = useState<SmtpSettings | null>(null);
  const [system, setSystem] = useState<SystemSettings | null>(null);
  const [templates, setTemplates] = useState<EmailTemplates>({
    locale: "es",
    invite: emptyBlock(),
    reset: emptyBlock(),
  });
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [langSaving, setLangSaving] = useState(false);

  useEffect(() => {
    getSmtpSettings()
      .then((s) => {
        setSettings(s);
        if (s.email_templates) setTemplates(s.email_templates);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("common", "error", "Error"))));
    getSystemSettings()
      .then(setSystem)
      .catch(() => undefined);
  }, [t]);

  async function onSaveSmtpTemplates(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setError(null);
    try {
      const saved = await updateSmtpSettings({
        ...settings,
        password: password || undefined,
        email_templates: { ...templates, locale },
      });
      setSettings(saved);
      if (saved.email_templates) setTemplates(saved.email_templates);
      setPassword("");
      setInfo(t("settings", "saved"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"));
    }
  }

  async function onTest() {
    if (!settings) return;
    setInfo(null);
    try {
      const r = await testSmtpSettings({ ...settings, password: password || undefined });
      setInfo(r.ok ? t("settings", "testOk") : `${t("common", "failedPrefix")}: ${r.detail}`);
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    }
  }

  async function onChangeAppLanguage(code: string) {
    setLangSaving(true);
    setError(null);
    try {
      await setTenantLocale(code);
      await setLocale(code);
      const s = await getSmtpSettings();
      setSettings(s);
      if (s.email_templates) setTemplates(s.email_templates);
      setInfo(t("settings", "localeSaved"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    } finally {
      setLangSaving(false);
    }
  }

  if (!settings) {
    return (
      <AppLayout>
        <Typography>{t("common", "loading")}</Typography>
      </AppLayout>
    );
  }

  const available = settings.available_locales?.length ? settings.available_locales : locales;
  const failedPrefix = t("common", "failedPrefix");

  return (
    <AppLayout>
      <PageShell
        title={t("settings", "title")}
        subtitle={t("settings", "subtitle")}
        alerts={
          <>
            {error && (
              <Alert severity="error" onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            {info && (
              <Alert
                severity={String(info).startsWith(failedPrefix) ? "warning" : "success"}
                onClose={() => setInfo(null)}
                sx={{ mt: error ? 1 : 0 }}
              >
                {info}
              </Alert>
            )}
          </>
        }
        filters={
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
            <Tab label={t("settings", "tabSmtp")} />
            <Tab label={t("settings", "tabTemplates")} />
            <Tab label={t("settings", "tabLanguage")} />
            <Tab label={t("settings", "tabData")} />
            <Tab label={t("settings", "tabAppearance")} />
          </Tabs>
        }
      >
      <Box component="form" onSubmit={onSaveSmtpTemplates}>
        {tab === 0 && (
          <Stack spacing={2}>
            <Typography color="text.secondary">{t("settings", "sectionSmtpHint")}</Typography>
            <TextField label={t("settings", "host")} value={settings.host} onChange={(e) => setSettings({ ...settings, host: e.target.value })} placeholder="mail.example.com" />
            <TextField
              label={t("settings", "port")}
              type="number"
              value={settings.port}
              onChange={(e) => setSettings({ ...settings, port: Number(e.target.value) })}
              helperText={t("settings", "portHint")}
            />
            <TextField label={t("settings", "user")} value={settings.user} onChange={(e) => setSettings({ ...settings, user: e.target.value })} />
            <TextField
              label={t("settings", "password")}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helperText={t("settings", "passwordHint")}
            />
            <TextField label={t("settings", "fromEmail")} value={settings.from_email} onChange={(e) => setSettings({ ...settings, from_email: e.target.value })} />
            <TextField label={t("settings", "fromName")} value={settings.from_name} onChange={(e) => setSettings({ ...settings, from_name: e.target.value })} />
            <FormControlLabel
              control={<Switch checked={settings.starttls} onChange={(e) => setSettings({ ...settings, starttls: e.target.checked })} />}
              label={t("settings", "starttls")}
            />
            <FormControlLabel
              control={<Switch checked={settings.enabled} onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })} />}
              label={t("settings", "enabled")}
            />
            <Stack direction="row" spacing={2}>
              <Button type="button" variant="outlined" onClick={onTest}>
                {t("settings", "test")}
              </Button>
              <Button type="submit" variant="contained">
                {t("common", "save")}
              </Button>
            </Stack>
          </Stack>
        )}

        {tab === 1 && (
          <Stack spacing={3}>
            <Typography color="text.secondary">{t("settings", "sectionTemplatesHint")}</Typography>
            <Alert severity="info">
              <Typography variant="subtitle2" fontWeight={600}>
                {t("settings", "templatesVarsTitle")}
              </Typography>
              <Typography variant="body2">{t("settings", "templatesVarsHelp")}</Typography>
            </Alert>
            <TemplateFields
              title={t("settings", "inviteTitle")}
              block={templates.invite}
              onChange={(invite) => setTemplates({ ...templates, invite })}
              labels={{
                subject: t("settings", "subject"),
                greeting: t("settings", "greeting"),
                intro: t("settings", "intro"),
                buttonLabel: t("settings", "buttonLabel"),
                footer: t("settings", "footer"),
                linkFallback: t("settings", "linkFallback"),
              }}
            />
            <TemplateFields
              title={t("settings", "resetTitle")}
              block={templates.reset}
              onChange={(reset) => setTemplates({ ...templates, reset })}
              labels={{
                subject: t("settings", "subject"),
                greeting: t("settings", "greeting"),
                intro: t("settings", "intro"),
                buttonLabel: t("settings", "buttonLabel"),
                footer: t("settings", "footer"),
                linkFallback: t("settings", "linkFallback"),
              }}
            />
            <Button type="submit" variant="contained" sx={{ alignSelf: "flex-start" }}>
              {t("common", "save")}
            </Button>
          </Stack>
        )}

        {tab === 2 && (
          <Stack spacing={2} maxWidth={480}>
            <Typography color="text.secondary">{t("settings", "sectionLanguageHint")}</Typography>
            <TextField
              select
              label={t("settings", "locale")}
              value={locale}
              disabled={langSaving}
              onChange={(e) => void onChangeAppLanguage(e.target.value)}
            >
              {available.map((l) => (
                <MenuItem key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </MenuItem>
              ))}
            </TextField>
            <Alert severity="info">{t("settings", "addLocaleHint")}</Alert>
          </Stack>
        )}

        {tab === 3 && (
          <Stack spacing={2} maxWidth={640}>
            <Typography color="text.secondary">{t("settings", "sectionDataHint")}</Typography>
            {system ? (
              <>
                <TextField
                  label={t("settings", "dataEngine")}
                  value={
                    system.db_engine === "sqlite"
                      ? t("settings", "dataEngineSqlite")
                      : system.db_engine === "mysql"
                        ? t("settings", "dataEngineMysql")
                        : system.db_engine
                  }
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
                <TextField
                  label={t("settings", "dataDbLabel")}
                  value={system.database_label}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
                {system.db_engine !== "sqlite" && system.mysql_host && (
                  <TextField
                    label={t("settings", "dataDbHost")}
                    value={`${system.mysql_host}:${system.mysql_port ?? ""}`}
                    fullWidth
                    InputProps={{ readOnly: true }}
                  />
                )}
                <TextField
                  label={t("settings", "dataStorageRoot")}
                  value={system.storage_root}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
                <TextField
                  label={t("settings", "dataAppEnv")}
                  value={system.app_env}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
              </>
            ) : (
              <Typography>{t("common", "loading")}</Typography>
            )}
            <Alert severity="info">{t("settings", "dataReadonlyNote")}</Alert>
            <Alert severity="warning">{t("settings", "dataComingSoon")}</Alert>
          </Stack>
        )}

        {tab === 4 && (
          <Stack spacing={2}>
            <Typography color="text.secondary">{t("settings", "sectionAppearanceHint")}</Typography>
            <Alert severity="info">{t("settings", "appearanceSoon")}</Alert>
          </Stack>
        )}
      </Box>
      </PageShell>
    </AppLayout>
  );
}
