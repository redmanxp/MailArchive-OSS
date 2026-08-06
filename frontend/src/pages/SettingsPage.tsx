/**
 * Admin settings: SMTP · Templates · Language · Data & storage · Microsoft · Appearance.
 */
import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
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
  getAppearance,
  getMicrosoftSettings,
  getSmtpSettings,
  getSystemSettings,
  resetBrandingLogo,
  setTenantLocale,
  testSmtpSettings,
  updateAppearance,
  updateMicrosoftSettings,
  updateSmtpSettings,
  updateSystemSettings,
  uploadBrandingLogo,
  type EmailTemplateBlock,
  type EmailTemplates,
  type MicrosoftSettings,
  type SmtpSettings,
  type SystemSettings,
} from "../api/client";
import BrandLogo from "../components/BrandLogo";
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

function syncDataFormFromSystem(s: SystemSettings) {
  return {
    dbEngine: s.db_engine === "mysql" ? "mysql" : "sqlite",
    mysqlHost: s.mysql_host || "",
    mysqlPort: s.mysql_port ?? 3306,
    mysqlUser: s.mysql_user || "",
    mysqlDatabase: s.mysql_database || "",
    storageRoot: s.storage_root || "",
  };
}

export default function SettingsPage() {
  const { t, setLocale, locales, locale } = useLocale();
  const [tab, setTab] = useState(0);
  const [settings, setSettings] = useState<SmtpSettings | null>(null);
  const [system, setSystem] = useState<SystemSettings | null>(null);
  const [microsoft, setMicrosoft] = useState<MicrosoftSettings | null>(null);
  const [templates, setTemplates] = useState<EmailTemplates>({
    locale: "es",
    invite: emptyBlock(),
    reset: emptyBlock(),
  });
  const [password, setPassword] = useState("");
  const [mysqlPassword, setMysqlPassword] = useState("");
  const [msSecret, setMsSecret] = useState("");
  const [dbEngine, setDbEngine] = useState("sqlite");
  const [mysqlHost, setMysqlHost] = useState("");
  const [mysqlPort, setMysqlPort] = useState(3306);
  const [mysqlUser, setMysqlUser] = useState("");
  const [mysqlDatabase, setMysqlDatabase] = useState("");
  const [storageRoot, setStorageRoot] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [langSaving, setLangSaving] = useState(false);
  const [dataSaving, setDataSaving] = useState(false);
  const [msSaving, setMsSaving] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [appearanceSaving, setAppearanceSaving] = useState(false);
  const [logoBust, setLogoBust] = useState(() => Date.now());
  const [hasCustomIcon, setHasCustomIcon] = useState(false);
  const [hasCustomFull, setHasCustomFull] = useState(false);

  useEffect(() => {
    getSmtpSettings()
      .then((s) => {
        setSettings(s);
        if (s.email_templates) setTemplates(s.email_templates);
      })
      .catch((e) => setError(String(e?.response?.data?.detail || t("common", "error", "Error"))));
    getSystemSettings()
      .then((s) => {
        setSystem(s);
        const synced = syncDataFormFromSystem(s);
        setDbEngine(synced.dbEngine);
        setMysqlHost(synced.mysqlHost);
        setMysqlPort(synced.mysqlPort);
        setMysqlUser(synced.mysqlUser);
        setMysqlDatabase(synced.mysqlDatabase);
        setStorageRoot(synced.storageRoot);
        setMysqlPassword("");
      })
      .catch(() => undefined);
    getMicrosoftSettings()
      .then(setMicrosoft)
      .catch(() => undefined);
    getAppearance()
      .then((a) => {
        setBrandName(a.brand_name || "");
        setPrimaryColor(a.primary_color || "");
        setHasCustomIcon(!!a.has_custom_logo_icon);
        setHasCustomFull(!!a.has_custom_logo_full);
        setLogoBust(Date.now());
      })
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

  async function onSaveData() {
    setDataSaving(true);
    setError(null);
    setInfo(null);
    try {
      const payload: Parameters<typeof updateSystemSettings>[0] = {
        storage_root: storageRoot,
        db_engine: dbEngine,
      };
      if (dbEngine === "mysql") {
        payload.mysql_host = mysqlHost;
        payload.mysql_port = Number(mysqlPort);
        payload.mysql_user = mysqlUser;
        payload.mysql_database = mysqlDatabase;
        if (mysqlPassword) payload.mysql_password = mysqlPassword;
      }
      const saved = await updateSystemSettings(payload);
      setSystem(saved);
      const synced = syncDataFormFromSystem(saved);
      setDbEngine(synced.dbEngine);
      setMysqlHost(synced.mysqlHost);
      setMysqlPort(synced.mysqlPort);
      setMysqlUser(synced.mysqlUser);
      setMysqlDatabase(synced.mysqlDatabase);
      setStorageRoot(synced.storageRoot);
      setMysqlPassword("");
      setInfo(saved.restart_required ? t("settings", "dataRestartRequired") : t("settings", "dataSaved"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    } finally {
      setDataSaving(false);
    }
  }

  async function onSaveMicrosoft() {
    if (!microsoft) return;
    setMsSaving(true);
    setError(null);
    setInfo(null);
    try {
      const saved = await updateMicrosoftSettings({
        client_id: microsoft.client_id,
        tenant_id: microsoft.tenant_id,
        redirect_uri: microsoft.redirect_uri,
        ...(msSecret ? { client_secret: msSecret } : {}),
      });
      setMicrosoft(saved);
      setMsSecret("");
      setInfo(t("settings", "msSaved"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    } finally {
      setMsSaving(false);
    }
  }

  async function onSaveAppearance() {
    setAppearanceSaving(true);
    setError(null);
    setInfo(null);
    try {
      const saved = await updateAppearance({
        brand_name: brandName,
        primary_color: primaryColor,
      });
      setBrandName(saved.brand_name || "");
      setPrimaryColor(saved.primary_color || "");
      setHasCustomIcon(!!saved.has_custom_logo_icon);
      setHasCustomFull(!!saved.has_custom_logo_full);
      setInfo(t("settings", "appearanceSaved"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    } finally {
      setAppearanceSaving(false);
    }
  }

  async function onUploadLogo(kind: "icon" | "full", file: File | null) {
    if (!file) return;
    setError(null);
    setInfo(null);
    try {
      await uploadBrandingLogo(kind, file);
      const a = await getAppearance();
      setHasCustomIcon(!!a.has_custom_logo_icon);
      setHasCustomFull(!!a.has_custom_logo_full);
      setLogoBust(Date.now());
      setInfo(t("settings", "logoUploaded"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
    }
  }

  async function onResetLogo(kind: "icon" | "full") {
    setError(null);
    try {
      await resetBrandingLogo(kind);
      const a = await getAppearance();
      setHasCustomIcon(!!a.has_custom_logo_icon);
      setHasCustomFull(!!a.has_custom_logo_full);
      setLogoBust(Date.now());
      setInfo(t("settings", "logoReset"));
    } catch (err: unknown) {
      setError(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("common", "error")));
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
                severity={
                  String(info).startsWith(failedPrefix) || info === t("settings", "dataRestartRequired")
                    ? "warning"
                    : "success"
                }
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
            <Tab label={t("settings", "tabMicrosoft")} />
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
            <TextField
              label={t("settings", "replyTo")}
              value={settings.reply_to || ""}
              onChange={(e) => setSettings({ ...settings, reply_to: e.target.value })}
              helperText={t("settings", "replyToHint")}
            />
            <TextField
              label={t("settings", "timeoutSeconds")}
              type="number"
              value={settings.timeout_seconds ?? 30}
              onChange={(e) => setSettings({ ...settings, timeout_seconds: Number(e.target.value) })}
              helperText={t("settings", "timeoutHint")}
              inputProps={{ min: 5, max: 120 }}
            />
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
                  select
                  label={t("settings", "dataEngine")}
                  value={dbEngine}
                  onChange={(e) => setDbEngine(e.target.value)}
                  fullWidth
                >
                  <MenuItem value="sqlite">{t("settings", "dataEngineSqlite")}</MenuItem>
                  <MenuItem value="mysql">{t("settings", "dataEngineMysql")}</MenuItem>
                </TextField>
                {dbEngine === "mysql" && (
                  <>
                    <TextField
                      label={t("settings", "dataDbHost")}
                      value={mysqlHost}
                      onChange={(e) => setMysqlHost(e.target.value)}
                      fullWidth
                    />
                    <TextField
                      label={t("settings", "port")}
                      type="number"
                      value={mysqlPort}
                      onChange={(e) => setMysqlPort(Number(e.target.value))}
                      fullWidth
                    />
                    <TextField
                      label={t("settings", "dataDbUser")}
                      value={mysqlUser}
                      onChange={(e) => setMysqlUser(e.target.value)}
                      fullWidth
                    />
                    <TextField
                      label={t("settings", "dataDbName")}
                      value={mysqlDatabase}
                      onChange={(e) => setMysqlDatabase(e.target.value)}
                      fullWidth
                    />
                    <TextField
                      label={t("settings", "dataDbPassword")}
                      type="password"
                      value={mysqlPassword}
                      onChange={(e) => setMysqlPassword(e.target.value)}
                      helperText={t("settings", "dataDbPasswordHint")}
                      fullWidth
                    />
                  </>
                )}
                <TextField
                  label={t("settings", "dataStorageRoot")}
                  value={storageRoot}
                  onChange={(e) => setStorageRoot(e.target.value)}
                  fullWidth
                />
                <TextField
                  label={t("settings", "dataDbLabel")}
                  value={system.database_label}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
                <TextField
                  label={t("settings", "dataAppEnv")}
                  value={system.app_env}
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
                <Button type="button" variant="contained" disabled={dataSaving} onClick={() => void onSaveData()} sx={{ alignSelf: "flex-start" }}>
                  {t("settings", "dataSave")}
                </Button>
              </>
            ) : (
              <Typography>{t("common", "loading")}</Typography>
            )}
          </Stack>
        )}

        {tab === 4 && (
          <Stack spacing={2} maxWidth={640}>
            <Typography color="text.secondary">{t("settings", "sectionMicrosoftHint")}</Typography>
            {microsoft ? (
              <>
                <Chip
                  label={microsoft.configured ? t("settings", "msConfigured") : t("settings", "msNotConfigured")}
                  color={microsoft.configured ? "success" : "warning"}
                  sx={{ alignSelf: "flex-start" }}
                />
                <TextField
                  label={t("settings", "msClientId")}
                  value={microsoft.client_id}
                  onChange={(e) => setMicrosoft({ ...microsoft, client_id: e.target.value })}
                  fullWidth
                />
                <TextField
                  label={t("settings", "msTenantId")}
                  value={microsoft.tenant_id}
                  onChange={(e) => setMicrosoft({ ...microsoft, tenant_id: e.target.value })}
                  fullWidth
                />
                <TextField
                  label={t("settings", "msRedirect")}
                  value={microsoft.redirect_uri}
                  onChange={(e) => setMicrosoft({ ...microsoft, redirect_uri: e.target.value })}
                  fullWidth
                />
                <TextField
                  label={t("settings", "msSecret")}
                  type="password"
                  value={msSecret}
                  onChange={(e) => setMsSecret(e.target.value)}
                  helperText={t("settings", "msSecretHint")}
                  fullWidth
                />
                <Button type="button" variant="contained" disabled={msSaving} onClick={() => void onSaveMicrosoft()} sx={{ alignSelf: "flex-start" }}>
                  {t("settings", "msSave")}
                </Button>
              </>
            ) : (
              <Typography>{t("common", "loading")}</Typography>
            )}
          </Stack>
        )}

        {tab === 5 && (
          <Stack spacing={2} maxWidth={560}>
            <Typography color="text.secondary">{t("settings", "sectionAppearanceHint")}</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={3} alignItems="center">
              <Box sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, bgcolor: "#fff" }}>
                <BrandLogo kind="icon" height={64} maxWidth={64} cacheBust={logoBust} />
              </Box>
              <Box sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, bgcolor: "#fff" }}>
                <BrandLogo kind="full" height={120} maxWidth={200} cacheBust={logoBust} />
              </Box>
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <Button variant="outlined" component="label">
                {t("settings", "logoUploadIcon")}
                <input hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => void onUploadLogo("icon", e.target.files?.[0] || null)} />
              </Button>
              <Button variant="outlined" component="label">
                {t("settings", "logoUploadFull")}
                <input hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => void onUploadLogo("full", e.target.files?.[0] || null)} />
              </Button>
            </Stack>
            <Stack direction="row" spacing={2}>
              {hasCustomIcon && (
                <Button size="small" onClick={() => void onResetLogo("icon")}>
                  {t("settings", "logoResetIcon")}
                </Button>
              )}
              {hasCustomFull && (
                <Button size="small" onClick={() => void onResetLogo("full")}>
                  {t("settings", "logoResetFull")}
                </Button>
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {t("settings", "logoHint")}
            </Typography>
            <TextField
              label={t("settings", "brandName")}
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              helperText={t("settings", "brandNameHint")}
              fullWidth
            />
            <TextField
              label={t("settings", "primaryColor")}
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              helperText={t("settings", "primaryColorHint")}
              placeholder="#0B3D5C"
              fullWidth
            />
            <Button
              type="button"
              variant="contained"
              disabled={appearanceSaving}
              onClick={() => void onSaveAppearance()}
              sx={{ alignSelf: "flex-start" }}
            >
              {t("settings", "appearanceSave")}
            </Button>
          </Stack>
        )}
      </Box>
      </PageShell>
    </AppLayout>
  );
}
