import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 15000,
});

export type UserPublic = {
  id: number;
  tenant_id: number;
  name: string;
  email: string;
  role: string;
  must_change_password: boolean;
};

export type UserAdmin = UserPublic & {
  status: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  must_change_password: boolean;
  user?: UserPublic;
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ma_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem("ma_refresh_token");
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenResponse>(
      `${import.meta.env.VITE_API_URL || ""}/api/v1/auth/refresh`,
      { refresh_token: refresh },
      { timeout: 15000 }
    );
    localStorage.setItem("ma_access_token", data.access_token);
    if (data.refresh_token) localStorage.setItem("ma_refresh_token", data.refresh_token);
    return data.access_token;
  } catch {
    localStorage.removeItem("ma_access_token");
    localStorage.removeItem("ma_refresh_token");
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error?.config as { _maRetry?: boolean; url?: string; headers?: Record<string, string> } | undefined;
    if (!original || error?.response?.status !== 401 || original._maRetry) {
      return Promise.reject(error);
    }
    const url = String(original.url || "");
    if (url.includes("/auth/login") || url.includes("/auth/refresh") || url.includes("/auth/logout")) {
      return Promise.reject(error);
    }
    original._maRetry = true;
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const token = await refreshPromise;
    if (!token) return Promise.reject(error);
    original.headers = original.headers || {};
    original.headers.Authorization = `Bearer ${token}`;
    return api.request(original);
  }
);

export type EmailTemplateBlock = {
  subject: string;
  greeting: string;
  intro: string;
  button_label: string;
  footer: string;
  link_fallback: string;
};

export type EmailTemplates = {
  locale: string;
  invite: EmailTemplateBlock;
  reset: EmailTemplateBlock;
};

export type SmtpSettings = {
  host: string;
  port: number;
  user: string;
  from_email: string;
  from_name: string;
  reply_to?: string;
  timeout_seconds?: number;
  starttls: boolean;
  enabled: boolean;
  configured: boolean;
  email_templates?: EmailTemplates;
  available_locales?: { code: string; name: string }[];
  ui_locale?: string;
};

export async function getInstallStatus() {
  const { data } = await api.get<{
    installed: boolean;
    public_register_enabled?: boolean;
    ui_locale?: string;
    db_engine?: string;
    storage_root?: string;
    restart_required?: boolean;
    tenant_mode?: "single" | "multi";
  }>("/api/v1/install/status");
  return data;
}

export async function setTenantLocale(locale: string) {
  const { data } = await api.put<{ message: string }>("/api/v1/i18n/tenant-locale", { locale });
  return data;
}

export type AppearanceSettings = {
  brand_name: string;
  primary_color: string;
  has_custom_logo_icon?: boolean;
  has_custom_logo_full?: boolean;
  logo_icon_url?: string;
  logo_full_url?: string;
};

export async function getAppearance() {
  const { data } = await api.get<AppearanceSettings>("/api/v1/i18n/appearance");
  return data;
}

export async function updateAppearance(payload: Partial<AppearanceSettings>) {
  const { data } = await api.put<AppearanceSettings>("/api/v1/i18n/appearance", payload);
  return data;
}

export async function uploadBrandingLogo(kind: "icon" | "full", file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ message: string }>(`/api/v1/branding/logo/${kind}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function resetBrandingLogo(kind: "icon" | "full") {
  const { data } = await api.delete<{ message: string }>(`/api/v1/branding/logo/${kind}`);
  return data;
}

export async function installApp(payload: {
  tenant_name: string;
  tenant_slug: string;
  admin_name: string;
  admin_email: string;
  admin_password?: string;
  storage_root?: string;
  db_engine?: string;
  mysql_host?: string;
  mysql_port?: number;
  mysql_user?: string;
  mysql_database?: string;
  mysql_password?: string;
  tenant_mode?: "single" | "multi";
}) {
  const { data } = await api.post("/api/v1/install", payload);
  return data as {
    tenant_id: number;
    tenant_slug: string;
    admin_id: number;
    admin_email: string;
    temporary_password: string;
    must_change_password: boolean;
  };
}

export async function login(email: string, password: string, tenant_slug?: string) {
  const { data } = await api.post<TokenResponse>("/api/v1/auth/login", {
    email,
    password,
    tenant_slug,
  });
  return data;
}

export async function selfRegister(payload: {
  name: string;
  email: string;
  tenant_slug?: string;
}) {
  const { data } = await api.post<{
    id: number;
    name: string;
    email: string;
    role: string;
    email_sent: boolean;
    email_detail: string;
    action: string;
    message: string;
  }>("/api/v1/auth/register", payload);
  return data;
}

export async function previewPasswordLink(token: string) {
  const { data } = await api.get<{ name: string; email: string; purpose: string }>(
    "/api/v1/auth/password-link",
    { params: { token } }
  );
  return data;
}

export async function completePasswordLink(token: string, new_password: string) {
  const { data } = await api.post<{
    id: number;
    email: string;
    must_change_password: boolean;
    message: string;
  }>("/api/v1/auth/password-link/complete", { token, new_password });
  return data;
}

export async function changePassword(current_password: string, new_password: string) {
  const { data } = await api.post("/api/v1/auth/change-password", {
    current_password,
    new_password,
  });
  return data;
}

export async function me() {
  const { data } = await api.get<UserPublic>("/api/v1/auth/me");
  return data;
}

export async function updateMyProfile(name: string) {
  const { data } = await api.patch<UserPublic>("/api/v1/auth/me", { name });
  return data;
}

export async function listUsers(opts?: { deleted?: boolean }) {
  const { data } = await api.get<UserAdmin[]>("/api/v1/admin/users", {
    params: opts?.deleted ? { deleted: true } : undefined,
  });
  return data;
}

export async function createUser(payload: {
  name: string;
  email: string;
  role: string;
  password?: string;
  must_change_password?: boolean;
  send_welcome_email?: boolean;
}) {
  const { data } = await api.post<{
    id: number;
    name: string;
    email: string;
    role: string;
    status: string;
    must_change_password: boolean;
    email_sent: boolean;
    email_detail: string;
    setup_url?: string;
  }>("/api/v1/admin/users", payload);
  return data;
}

export async function updateUser(
  userId: number,
  payload: { name?: string; role?: string; status?: string }
) {
  const { data } = await api.patch<UserAdmin>(`/api/v1/admin/users/${userId}`, payload);
  return data;
}

export async function resetUserPassword(userId: number, send_email = true) {
  const { data } = await api.post<{
    id: number;
    email: string;
    email_sent: boolean;
    email_detail: string;
    setup_url?: string;
  }>(`/api/v1/admin/users/${userId}/reset-password`, {
    new_password: null,
    send_email,
    must_change_password: true,
  });
  return data;
}

export async function deactivateUser(
  userId: number,
  opts?: { accounts_action?: "unlink" | "transfer"; transfer_to_user_id?: number }
) {
  const { data } = await api.post<{ message: string }>(`/api/v1/admin/users/${userId}/deactivate`, {
    accounts_action: opts?.accounts_action || "unlink",
    transfer_to_user_id: opts?.transfer_to_user_id,
  });
  return data;
}

export async function restoreUser(userId: number) {
  const { data } = await api.post<UserAdmin>(`/api/v1/admin/users/${userId}/restore`);
  return data;
}

export async function hardDeleteUser(userId: number, reassign_to_user_id?: number) {
  const { data } = await api.post<{ message: string }>(`/api/v1/admin/users/${userId}/hard-delete`, {
    reassign_to_user_id: reassign_to_user_id ?? null,
  });
  return data;
}

export type DeparturePreview = {
  user: UserAdmin;
  accounts: { id: number; email: string; provider: string; status: string }[];
};

export type DepartureResult = {
  user_id: number;
  email: string;
  deactivated: boolean;
  accounts_action: string;
  accounts_touched: number;
  mails_reassigned: number;
  job_ids: number[];
  archive_skipped: { account_id: number; email: string; reason: string }[];
  schedules_disabled: number;
};

export async function getDeparturePreview(userId: number) {
  const { data } = await api.get<DeparturePreview>(`/api/v1/admin/users/${userId}/departure`);
  return data;
}

export async function runEmployeeDeparture(
  userId: number,
  payload: {
    accounts_action: "unlink" | "transfer";
    transfer_to_user_id?: number;
    archive_enabled?: boolean;
    older_than_days?: number | null;
    archive_limit?: number;
    disable_schedules?: boolean;
  }
) {
  const { data } = await api.post<DepartureResult>(`/api/v1/admin/users/${userId}/departure`, payload);
  return data;
}

export async function getSmtpSettings() {
  const { data } = await api.get<SmtpSettings>("/api/v1/admin/settings/smtp");
  return data;
}

export type SystemSettings = {
  app_env: string;
  db_engine: string;
  database_label: string;
  mysql_host?: string | null;
  mysql_port?: number | null;
  mysql_database?: string | null;
  mysql_user?: string | null;
  storage_root: string;
  storage_backend?: string;
  s3_endpoint_url?: string;
  s3_access_key?: string;
  s3_bucket?: string;
  s3_region?: string;
  s3_force_path_style?: boolean;
  s3_prefix?: string;
  s3_secret_set?: boolean;
  editable: boolean;
  restart_required?: boolean;
  mysql_password_set?: boolean;
  tenant_mode?: "single" | "multi";
  tenant_count?: number;
};

export async function getSystemSettings() {
  const { data } = await api.get<SystemSettings>("/api/v1/admin/settings/system");
  return data;
}

export async function updateSystemSettings(
  payload: Partial<{
    storage_root: string;
    storage_backend: string;
    s3_endpoint_url: string;
    s3_access_key: string;
    s3_secret_key: string;
    s3_bucket: string;
    s3_region: string;
    s3_force_path_style: boolean;
    s3_prefix: string;
    db_engine: string;
    mysql_host: string;
    mysql_port: number;
    mysql_user: string;
    mysql_database: string;
    mysql_password: string;
    tenant_mode: "single" | "multi";
  }>
) {
  const { data } = await api.put<SystemSettings>("/api/v1/admin/settings/system", payload);
  return data;
}

export type MicrosoftSettings = {
  client_id: string;
  tenant_id: string;
  redirect_uri: string;
  configured: boolean;
  secret_set: boolean;
};

export async function getMicrosoftSettings() {
  const { data } = await api.get<MicrosoftSettings>("/api/v1/admin/settings/microsoft");
  return data;
}

export async function updateMicrosoftSettings(
  payload: Partial<{
    client_id: string;
    tenant_id: string;
    redirect_uri: string;
    client_secret: string;
  }>
) {
  const { data } = await api.put<MicrosoftSettings>("/api/v1/admin/settings/microsoft", payload);
  return data;
}

export type DashboardMetrics = {
  tenant_id: number;
  scope: string;
  users_count: number | null;
  accounts_count: number;
  mails_count: number;
  storage_bytes: number;
  attachments_count: number;
  jobs_active: number;
  jobs_failed: number;
  schedules_with_errors: number;
  last_archive_at?: string | null;
  health: {
    db_ok: boolean;
    storage_ok: boolean;
    storage_root?: string | null;
  } | null;
  generated_at: string;
};

export async function getDashboardMetrics() {
  const { data } = await api.get<DashboardMetrics>("/api/v1/dashboard/metrics");
  return data;
}

export async function updateSmtpSettings(payload: Partial<SmtpSettings> & { password?: string }) {
  const { data } = await api.put<SmtpSettings>("/api/v1/admin/settings/smtp", payload);
  return data;
}

export async function testSmtpSettings(payload?: Partial<SmtpSettings> & { password?: string }) {
  const { data } = await api.post<{ ok: boolean; detail: string }>(
    "/api/v1/admin/settings/smtp/test",
    payload ?? {}
  );
  return data;
}

export type AuditLogItem = {
  id: number;
  action: string;
  user_id?: number | null;
  resource_type?: string | null;
  resource_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
};

export async function listAuditLogs(params?: { q?: string; limit?: number; offset?: number }) {
  const { data } = await api.get<{
    items: AuditLogItem[];
    total: number;
    limit: number;
    offset: number;
  }>("/api/v1/admin/audit-logs", { params });
  return data;
}

export async function clearAuditLogs() {
  const { data } = await api.delete<{ message: string }>("/api/v1/admin/audit-logs");
  return data;
}

export async function logout(refresh_token: string) {
  await api.post("/api/v1/auth/logout", { refresh_token });
}

export type AccountPublic = {
  id: number;
  user_id: number;
  provider: string;
  email: string;
  display_name?: string | null;
  status: string;
  last_sync_at?: string | null;
  last_error?: string | null;
  linked_at?: string | null;
  owner_email?: string | null;
  owner_name?: string | null;
  is_mine?: boolean;
  imap_host?: string | null;
  imap_port?: number | null;
  imap_ssl?: boolean | null;
  imap_username?: string | null;
  archived_count?: number | null;
  schedule_enabled?: boolean;
};

export async function listAccounts(opts?: { status?: "active" | "unlinked" }) {
  const { data } = await api.get<AccountPublic[]>("/api/v1/accounts", {
    params: opts?.status ? { status: opts.status } : undefined,
  });
  return data;
}

export async function testImapConnection(payload: {
  host: string;
  port: number;
  ssl: boolean;
  username: string;
  password: string;
}) {
  const { data } = await api.post<{ ok: boolean; detail: string; email?: string }>(
    "/api/v1/accounts/imap/test",
    payload
  );
  return data;
}

export async function createImapAccount(payload: {
  host: string;
  port: number;
  ssl: boolean;
  username: string;
  password: string;
  email?: string;
}) {
  const { data } = await api.post("/api/v1/accounts/imap", payload);
  return data;
}

export async function startMicrosoftOAuth() {
  const { data } = await api.get<{ authorize_url: string }>("/api/v1/accounts/microsoft/oauth/start");
  return data;
}

export async function deleteAccount(accountId: number) {
  const { data } = await api.delete<{ id: number; status: string; kept_archive: boolean }>(
    `/api/v1/accounts/${accountId}`
  );
  return data;
}

export async function reconnectImapAccount(
  accountId: number,
  payload: {
    host: string;
    port: number;
    ssl: boolean;
    username: string;
    password: string;
  }
) {
  const { data } = await api.post<{
    id: number;
    email: string;
    status: string;
    test_ok: boolean;
    test_detail: string;
  }>(`/api/v1/accounts/${accountId}/reconnect/imap`, payload);
  return data;
}

export async function hardDeleteAccount(accountId: number) {
  const { data } = await api.post<{ id: number; email: string; jobs_deleted: number }>(
    `/api/v1/accounts/${accountId}/hard-delete`
  );
  return data;
}

export async function purgeAccountArchive(accountId: number, confirm: string) {
  const { data } = await api.post<{
    id: number;
    email: string;
    mails_deleted: number;
    jobs_deleted: number;
    storage_errors: number;
  }>(`/api/v1/accounts/${accountId}/purge-archive`, { confirm });
  return data;
}

export async function transferAccount(accountId: number, newUserId: number, reassignMails = true) {
  const { data } = await api.post<{
    id: number;
    from_user_id: number;
    to_user_id: number;
    mails_reassigned: number;
    jobs_reassigned: number;
  }>(`/api/v1/accounts/${accountId}/transfer`, {
    new_user_id: newUserId,
    reassign_mails: reassignMails,
  });
  return data;
}

export type ArchiveSchedule = {
  account_id: number;
  enabled: boolean;
  interval_minutes: number;
  folder_id?: string | null;
  folder_path?: string | null;
  limit_per_run: number;
  only_with_attachments: boolean;
  historical_backfill?: boolean;
  watermark_at?: string | null;
  backfill_watermark_at?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_job_id?: number | null;
  last_status?: string | null;
  last_error?: string | null;
};

export async function getAccountSchedule(accountId: number) {
  const { data } = await api.get<ArchiveSchedule>(`/api/v1/accounts/${accountId}/schedule`);
  return data;
}

export async function updateAccountSchedule(
  accountId: number,
  payload: {
    enabled: boolean;
    interval_minutes: number;
    folder_id?: string | null;
    folder_path?: string | null;
    limit_per_run: number;
    only_with_attachments: boolean;
    historical_backfill?: boolean;
  }
) {
  const { data } = await api.put<ArchiveSchedule>(`/api/v1/accounts/${accountId}/schedule`, payload);
  return data;
}

export async function runAccountScheduleNow(accountId: number) {
  const { data } = await api.post<ArchiveSchedule & { job_id?: number | null }>(
    `/api/v1/accounts/${accountId}/schedule/run`
  );
  return data;
}

export type FolderPublic = {
  id: string;
  name: string;
  path: string;
  total_items?: number | null;
};

export type ProviderMessage = {
  id: string;
  subject: string;
  from_address: string;
  to_addresses: string[];
  sent_at?: string | null;
  received_at?: string | null;
  size_bytes: number;
  has_attachments: boolean;
  folder: string;
};

export type ArchivedMail = {
  id: string;
  account_id: number;
  subject: string;
  from_address: string;
  to_addresses?: string | null;
  sent_at?: string | null;
  has_attachments: boolean;
  size_bytes: number;
  archived_at?: string | null;
  body_preview?: string | null;
  deleted_from_provider?: boolean;
  restored_at?: string | null;
};

export type ArchivedMailDetail = ArchivedMail & {
  user_id: number;
  provider_message_id: string;
  folder_path: string;
  cc_addresses?: string | null;
  received_at?: string | null;
  content_sha256: string;
  body_text?: string | null;
  body_html?: string | null;
  body_is_html?: boolean;
  attachment_names?: string | null;
  attachments: Array<{
    id: number;
    filename: string;
    content_type: string;
    size_bytes: number;
  }>;
};

export async function listAccountFolders(accountId: number) {
  const { data } = await api.get<FolderPublic[]>(`/api/v1/accounts/${accountId}/folders`);
  return data;
}

export async function listAccountMessages(
  accountId: number,
  params?: { folder_id?: string; limit?: number; only_with_attachments?: boolean }
) {
  const { data } = await api.get<ProviderMessage[]>(`/api/v1/accounts/${accountId}/messages`, {
    params,
    timeout: 60000,
  });
  return data;
}

export type ProviderMessageDetail = ProviderMessage & {
  body_text?: string | null;
  body_html?: string | null;
  body_is_html?: boolean;
  body_preview?: string | null;
  attachments?: Array<{
    id: number;
    filename: string;
    content_type: string;
    size_bytes: number;
  }>;
};

export async function previewProviderMessage(
  accountId: number,
  messageId: string,
  folderId?: string
) {
  const { data } = await api.get<ProviderMessageDetail>(
    `/api/v1/accounts/${accountId}/messages/${encodeURIComponent(messageId)}`,
    { params: folderId ? { folder_id: folderId } : undefined, timeout: 120000 }
  );
  return data;
}

export async function downloadProviderAttachment(
  accountId: number,
  messageId: string,
  attachmentId: number,
  folderId?: string
) {
  const { data, headers } = await api.get<Blob>(
    `/api/v1/accounts/${accountId}/messages/${encodeURIComponent(messageId)}/attachments/${attachmentId}/download`,
    {
      params: folderId ? { folder_id: folderId } : undefined,
      responseType: "blob",
      timeout: 120000,
    }
  );
  const disposition = headers["content-disposition"] as string | undefined;
  let filename = `adjunto-${attachmentId}`;
  if (disposition) {
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
    if (m) filename = decodeURIComponent(m[1] || m[2]);
  }
  return { blob: data, filename };
}

export async function downloadProviderAttachmentToDisk(
  accountId: number,
  messageId: string,
  attachmentId: number,
  folderId?: string
) {
  const { blob, filename } = await downloadProviderAttachment(accountId, messageId, attachmentId, folderId);
  triggerBlobDownload(blob, filename);
}

export async function archiveMessage(payload: {
  account_id: number;
  message_id: string;
  folder_id?: string;
  folder_path?: string;
  delete_after_archive?: boolean;
}) {
  const { data } = await api.post<{
    id: string;
    subject: string;
    size_bytes: number;
    content_sha256: string;
    deleted_from_provider: boolean;
    storage_path: string;
    already_archived?: boolean;
  }>("/api/v1/archive/messages", payload, { timeout: 120000 });
  return data;
}

export async function searchMails(params?: {
  q?: string;
  account_id?: number;
  from_address?: string;
  has_attachments?: boolean;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}) {
  const { data } = await api.get<{
    items: ArchivedMail[];
    total: number;
    limit: number;
    offset: number;
  }>("/api/v1/mails/search", { params });
  return data;
}

export async function searchMailIds(params?: {
  q?: string;
  account_id?: number;
  from_address?: string;
  has_attachments?: boolean;
  date_from?: string;
  date_to?: string;
  limit?: number;
}) {
  const { data } = await api.get<{ ids: string[]; total: number; limit: number }>(
    "/api/v1/mails/search/ids",
    { params, timeout: 60000 }
  );
  return data;
}

export async function bulkDownloadArchivedMails(mailIds: string[]) {
  const { data, headers } = await api.post<Blob>(
    "/api/v1/mails/bulk/download",
    { mail_ids: mailIds },
    { responseType: "blob", timeout: 300000 }
  );
  const disposition = headers["content-disposition"] as string | undefined;
  let filename = "archivados.zip";
  if (disposition) {
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
    if (m) filename = decodeURIComponent(m[1] || m[2]);
  }
  return { blob: data, filename };
}

export async function bulkDownloadArchivedMailsToDisk(mailIds: string[]) {
  const { blob, filename } = await bulkDownloadArchivedMails(mailIds);
  triggerBlobDownload(blob, filename);
}

export async function bulkRestoreArchivedMails(mailIds: string[], keepCopy = false) {
  const { data } = await api.post<{
    restored: number;
    failed: Array<{ id: string; error: string }>;
    requested: number;
    kept_in_archive: boolean;
  }>(
    "/api/v1/mails/bulk/restore",
    { mail_ids: mailIds, keep_copy: keepCopy },
    { timeout: 600000 }
  );
  return data;
}

export async function bulkDeleteArchivedMails(mailIds: string[]) {
  const { data } = await api.post<{
    deleted: number;
    failed: Array<{ id: string; error: string }>;
    requested: number;
  }>("/api/v1/mails/bulk/delete", { mail_ids: mailIds }, { timeout: 600000 });
  return data;
}

export async function deleteArchivedMail(mailId: string) {
  const { data } = await api.delete<{ id: string; deleted: boolean }>(`/api/v1/mails/${mailId}`);
  return data;
}

export async function getArchivedMail(mailId: string) {
  const { data } = await api.get<ArchivedMailDetail>(`/api/v1/mails/${mailId}`);
  return data;
}

export async function downloadArchivedEml(mailId: string) {
  const { data, headers } = await api.get<Blob>(`/api/v1/mails/${mailId}/download`, {
    responseType: "blob",
  });
  const disposition = headers["content-disposition"] as string | undefined;
  let filename = `mail-${mailId}.eml`;
  if (disposition) {
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
    if (m) filename = decodeURIComponent(m[1] || m[2]);
  }
  return { blob: data, filename };
}

export async function downloadArchivedAttachment(mailId: string, attachmentId: number) {
  const { data, headers } = await api.get<Blob>(
    `/api/v1/mails/${mailId}/attachments/${attachmentId}/download`,
    { responseType: "blob" }
  );
  const disposition = headers["content-disposition"] as string | undefined;
  let filename = `attachment-${attachmentId}`;
  if (disposition) {
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
    if (m) filename = decodeURIComponent(m[1] || m[2]);
  }
  return { blob: data, filename };
}

export async function restoreArchivedMail(mailId: string, opts?: { folder_id?: string; keep_copy?: boolean }) {
  const { data } = await api.post<{
    id: string;
    provider_message_id: string;
    folder: string;
    account_id: number;
    kept_in_archive: boolean;
  }>(
    `/api/v1/mails/${mailId}/restore`,
    { folder_id: opts?.folder_id, keep_copy: Boolean(opts?.keep_copy) },
    { timeout: 120000 }
  );
  return data;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadEmlToDisk(mailId: string) {
  const { blob, filename } = await downloadArchivedEml(mailId);
  triggerBlobDownload(blob, filename);
}

export async function downloadAttachmentToDisk(mailId: string, attachmentId: number) {
  const { blob, filename } = await downloadArchivedAttachment(mailId, attachmentId);
  triggerBlobDownload(blob, filename);
}

export type ArchiveJobResult = {
  note?: string | null;
  archived?: number;
  skipped_already_archived?: number;
  failed?: number;
  archived_bytes?: number;
  skipped_samples?: { message_id?: string; subject?: string; reason?: string }[];
  archived_samples?: { message_id?: string; subject?: string }[];
  failed_samples?: { message_id?: string; subject?: string; error?: string }[];
  crash?: string;
};

export type ArchiveJob = {
  id: number;
  account_id: number;
  account_email?: string | null;
  user_id: number;
  status: string;
  criteria?: Record<string, unknown> | null;
  result?: ArchiveJobResult | null;
  delete_after_archive: boolean;
  total_messages: number;
  processed_messages: number;
  archived_messages: number;
  skipped_messages: number;
  failed_messages: number;
  total_bytes: number;
  archived_bytes: number;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  progress_pct: number;
};

export async function simulateBulkArchive(
  payload: {
    account_id: number;
    criteria: Record<string, unknown>;
    limit?: number;
  },
  opts?: { signal?: AbortSignal }
) {
  const { data } = await api.post<{
    account_id: number;
    message_count: number;
    total_bytes: number;
    messages: ProviderMessage[];
    sample: ProviderMessage[];
    criteria: Record<string, unknown>;
  }>("/api/v1/archive/jobs/simulate", payload, { timeout: 120000, signal: opts?.signal });
  return data;
}

export async function startBulkArchive(payload: {
  account_id: number;
  criteria: Record<string, unknown>;
  delete_after_archive?: boolean;
  limit?: number;
  message_ids?: string[];
  total_bytes_hint?: number;
}) {
  const { data } = await api.post<ArchiveJob>("/api/v1/archive/jobs", payload, { timeout: 120000 });
  return data;
}

export async function listArchiveJobs() {
  const { data } = await api.get<ArchiveJob[]>("/api/v1/archive/jobs");
  return data;
}

export async function getArchiveJob(jobId: number) {
  const { data } = await api.get<ArchiveJob>(`/api/v1/archive/jobs/${jobId}`);
  return data;
}

export async function cancelArchiveJob(jobId: number) {
  const { data } = await api.post<{ id: number; status: string }>(`/api/v1/archive/jobs/${jobId}/cancel`);
  return data;
}

export async function retryArchiveJob(jobId: number) {
  const { data } = await api.post<ArchiveJob>(`/api/v1/archive/jobs/${jobId}/retry`);
  return data;
}

export default api;
