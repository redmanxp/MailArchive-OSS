/**
 * Capture README / landing screenshots with PII redacted in the DOM.
 *
 *   cd frontend && node ../scripts/capture-screenshots.mjs
 *
 * Env: MA_BASE_URL MA_TENANT MA_EMAIL MA_PASSWORD MA_LOCALE
 * Replaces real emails, hostnames, person names, and mail subjects
 * with demo placeholders before each shot.
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

const DEMO_MAILBOXES = [
  "hr@example.com",
  "info@example.com",
  "legal@example.com",
  "archive@example.com",
  "sales@example.com",
  "support@example.com",
];
const DEMO_NAMES = ["User Demo", "Colleague Demo", "Owner Demo"];
const DEMO_SUBJECTS = [
  "Quarterly planning notes",
  "Invoice follow-up",
  "Meeting recap",
  "Project kickoff",
  "Weekly status",
  "Contract draft",
  "Welcome aboard",
  "Schedule update",
];

async function redactPii(page) {
  await page.evaluate(
    ({ demoMails, demoNames, demoSubjects }) => {
      const emailRe = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
      const hostRe =
        /\b(?:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|ar|es|uk|de|fr|edu|gov)(?:\.[a-z]{2})?)\b/gi;
      const keepHost = /^(localhost|example\.com|.*\.example\.com|minio|mailarchive-[a-z0-9-]+)$/i;
      const mailMap = new Map();
      let mailIdx = 0;
      let nameIdx = 0;
      let hostIdx = 0;
      const demoHosts = ["smtp.example.com", "mail.example.com", "imap.example.com"];
      const roleRe =
        /^(Administrator|Admin|Supervisor|User|Read-?only|Solo lectura|Administrador|Usuarios?)$/i;

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

      function maybeAddName(found, raw) {
        const name = (raw || "").trim();
        if (!name || name.includes("@") || roleRe.test(name) || /demo$/i.test(name)) return;
        if (name.split(/\s+/).length < 2 || name.length > 80) return;
        if (/^(sign out|sign in|mail archive|microsoft 365|active jobs)$/i.test(name)) return;
        found.add(name);
      }

      function collectPersonNames() {
        const found = new Set();
        const headers = [...document.querySelectorAll("th")];
        headers.forEach((th, idx) => {
          if (!/^(name|nombre|user|usuario|owner|dueño)$/i.test((th.innerText || "").trim())) return;
          document.querySelectorAll("tbody tr").forEach((tr) => {
            const td = tr.querySelectorAll("td")[idx];
            if (!td) return;
            for (const line of (td.innerText || "").split("\n")) maybeAddName(found, line);
          });
        });
        const aside =
          document.querySelector(".MuiDrawer-paper") ||
          document.querySelector("[class*='MuiDrawer-paper']") ||
          document.querySelector("aside, nav");
        if (aside) {
          const texts = [];
          const w = document.createTreeWalker(aside, NodeFilter.SHOW_TEXT);
          while (w.nextNode()) {
            const t = (w.currentNode.nodeValue || "").trim();
            if (t) texts.push(t);
          }
          const emailIdx = texts.findIndex((t) => {
            emailRe.lastIndex = 0;
            return emailRe.test(t);
          });
          if (emailIdx > 0) {
            for (let i = emailIdx - 1; i >= 0; i -= 1) {
              if (roleRe.test(texts[i]) || texts[i].includes("@")) continue;
              maybeAddName(found, texts[i]);
              break;
            }
          }
        }
        return [...found].sort((a, b) => b.length - a.length);
      }

      const knownNames = collectPersonNames();
      const nameMap = new Map();
      function mapName(raw) {
        const key = raw.toLowerCase();
        if (/demo$/i.test(raw)) return raw;
        if (!nameMap.has(key)) {
          nameMap.set(key, demoNames[nameIdx % demoNames.length]);
          nameIdx += 1;
        }
        return nameMap.get(key);
      }

      function scrubText(text) {
        if (!text) return text;
        let out = text.replace(emailRe, (m) => mapEmail(m));
        out = out.replace(hostRe, (m) => mapHost(m));
        for (const name of knownNames) {
          const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          out = out.replace(new RegExp(escaped, "gi"), () => mapName(name));
        }
        return out;
      }

      const headers = [...document.querySelectorAll("th")];
      const subjectIdx = headers.findIndex((th) => /subject|asunto/i.test(th.innerText || ""));
      if (subjectIdx >= 0) {
        document.querySelectorAll("tbody tr").forEach((tr, i) => {
          const td = tr.querySelectorAll("td")[subjectIdx];
          if (!td) return;
          td.querySelectorAll("*").forEach((el) => {
            if (el.childElementCount === 0 && (el.textContent || "").trim()) {
              el.textContent = demoSubjects[i % demoSubjects.length];
            }
          });
          if (!(td.textContent || "").trim()) return;
          if (![...td.querySelectorAll("*")].some((el) => (el.textContent || "").includes(demoSubjects[0]))) {
            td.textContent = demoSubjects[i % demoSubjects.length];
          }
        });
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
    { demoMails: DEMO_MAILBOXES, demoNames: DEMO_NAMES, demoSubjects: DEMO_SUBJECTS }
  );
}

async function shot(page, name) {
  await redactPii(page);
  await page.waitForTimeout(250);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file });
  console.log("wrote", file);
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await context.addInitScript((loc) => localStorage.setItem("ma_ui_locale", loc), locale);
const page = await context.newPage();

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
  ["/app/jobs", "jobs.png"],
  ["/app/bulk", "bulk.png"],
]) {
  await page.goto(`${base}${route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, name);
}

await page.goto(`${base}/app/mails`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const rowCheck = page.locator("tbody tr input[type=checkbox]").first();
if ((await rowCheck.count()) > 0) {
  await rowCheck.check({ force: true });
  const restoreBtn = page.getByRole("button", { name: /restore selected|restaurar seleccionados/i });
  if ((await restoreBtn.count()) > 0 && (await restoreBtn.isEnabled())) {
    await restoreBtn.click();
    await page.waitForTimeout(600);
    await shot(page, "restore.png");
  }
}

await browser.close();
