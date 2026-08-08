/**
 * Capture README screenshots with PII redacted in the DOM.
 *
 *   cd frontend && node ../scripts/capture-screenshots.mjs
 *
 * Env: MA_BASE_URL MA_TENANT MA_EMAIL MA_PASSWORD MA_LOCALE
 * Replaces real emails/names with @example.com placeholders before each shot.
 */
import { createRequire } from "module";
import { mkdir } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRequire = createRequire(path.join(__dirname, "../frontend/package.json"));
const { chromium } = frontendRequire("playwright");

const outDir = path.join(__dirname, "../docs/images");
const base = process.env.MA_BASE_URL || "http://127.0.0.1:8080";
const email = process.env.MA_EMAIL || "admin@example.com";
const password = process.env.MA_PASSWORD || "DemoPass123!";
const tenant = process.env.MA_TENANT || "demo";
const locale = process.env.MA_LOCALE || "en";

/** Stable demo labels for README (order of first appearance). */
const DEMO_MAILBOXES = [
  "hr@example.com",
  "info@example.com",
  "legal@example.com",
  "archive@example.com",
  "sales@example.com",
  "support@example.com",
];
const DEMO_NAMES = ["User Demo", "Colleague Demo", "Owner Demo"];

async function redactPii(page) {
  await page.evaluate(
    ({ demoMails, demoNames }) => {
      const emailRe = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
      // Real-looking hostnames (SMTP, IMAP, etc.) — keep example.com / localhost / minio / docker DNS
      const hostRe =
        /\b(?:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|ar|es|uk|de|fr|edu|gov)(?:\.[a-z]{2})?)\b/gi;
      const keepHost = /^(localhost|example\.com|.*\.example\.com|minio|mailarchive-[a-z0-9-]+)$/i;
      const mailMap = new Map();
      let mailIdx = 0;
      let nameIdx = 0;
      let hostIdx = 0;
      const demoHosts = ["smtp.example.com", "mail.example.com", "imap.example.com"];

      function mapEmail(raw) {
        const key = raw.toLowerCase();
        if (key.endsWith("@example.com")) return raw;
        if (!mailMap.has(key)) {
          mailMap.set(key, demoMails[mailIdx % demoMails.length]);
          mailIdx += 1;
        }
        return mailMap.get(key);
      }

      function mapHost(raw) {
        const key = raw.toLowerCase();
        if (keepHost.test(key) || key.endsWith(".example.com") || key === "example.com") return raw;
        return demoHosts[hostIdx++ % demoHosts.length];
      }

      function scrubText(text) {
        if (!text) return text;
        let out = text.replace(emailRe, (m) => mapEmail(m));
        out = out.replace(hostRe, (m) => mapHost(m));
        out = out.replace(/\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b/g, (full) => {
          const keep = /^(Admin Demo|Mail Archive|Microsoft|User Demo|Colleague Demo|Owner Demo)$/i;
          if (keep.test(full) || /Demo$/i.test(full)) return full;
          const replacement = demoNames[nameIdx % demoNames.length];
          nameIdx += 1;
          return replacement;
        });
        return out;
      }

      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(parent.tagName)) continue;
        const next = scrubText(node.nodeValue || "");
        if (next !== node.nodeValue) node.nodeValue = next;
      }

      for (const el of document.querySelectorAll("[title], [aria-label], [placeholder], input, textarea")) {
        for (const attr of ["title", "aria-label", "placeholder", "value"]) {
          if (!el.hasAttribute(attr) && attr !== "value") continue;
          const cur = attr === "value" && "value" in el ? el.value : el.getAttribute(attr);
          if (!cur) continue;
          const next = scrubText(cur);
          if (next === cur) continue;
          if (attr === "value" && "value" in el) el.value = next;
          else el.setAttribute(attr, next);
        }
      }
    },
    { demoMails: DEMO_MAILBOXES, demoNames: DEMO_NAMES }
  );
}

async function shot(page, name) {
  await redactPii(page);
  await page.waitForTimeout(200);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file });
  console.log("wrote", file);
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await context.addInitScript((loc) => localStorage.setItem("ma_ui_locale", loc), locale);
const page = await context.newPage();

// Tenant install status can override UI locale — force MA_LOCALE for README shots.
await page.route("**/api/v1/install/status", async (route) => {
  try {
    const res = await route.fetch();
    const json = await res.json();
    await route.fulfill({
      status: res.status(),
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...json, ui_locale: locale }),
    });
  } catch {
    await route.continue();
  }
});

await page.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("form input");
await page.waitForTimeout(1000);
await shot(page, "login.png");

const tenantInput = page.locator('form input[name="tenant"], form input[id*="tenant" i]').first();
const emailInput = page.locator('form input[type="email"], form input[name="email"]').first();
const passwordInput = page.locator('form input[type="password"]').first();

if ((await tenantInput.count()) > 0 && (await tenantInput.isVisible())) {
  await tenantInput.fill(tenant);
}
await emailInput.fill(email);
await passwordInput.fill(password);
await page.locator("form button[type=submit]").click();
await page.waitForURL(/\/app/, { timeout: 20000 });
await page.waitForTimeout(1200);
await shot(page, "dashboard.png");

for (const [route, name] of [
  ["/app/users", "users.png"],
  ["/app/settings", "settings.png"],
  ["/app/mails", "archive.png"],
  ["/app/accounts", "accounts.png"],
]) {
  await page.goto(`${base}${route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, name);
}

await browser.close();
