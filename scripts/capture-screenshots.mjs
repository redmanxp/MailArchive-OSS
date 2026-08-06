/**
 * Capture README screenshots (run from repo root or frontend):
 *
 *   cd frontend && node ../scripts/capture-screenshots.mjs
 *
 * Env: MA_BASE_URL MA_TENANT MA_EMAIL MA_PASSWORD MA_LOCALE
 */
import { createRequire } from "module";
import { mkdir } from "fs/promises";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRequire = createRequire(path.join(__dirname, "../frontend/package.json"));
const playwrightEntry = frontendRequire.resolve("playwright");
const { chromium } = await import(pathToFileURL(playwrightEntry).href);

const outDir = path.join(__dirname, "../docs/images");
const base = process.env.MA_BASE_URL || "http://127.0.0.1:8080";
const email = process.env.MA_EMAIL || "admin@example.com";
const password = process.env.MA_PASSWORD || "DemoPass123!";
const tenant = process.env.MA_TENANT || "demo";
const locale = process.env.MA_LOCALE || "en";

async function shot(page, name) {
  const file = path.join(outDir, name);
  await page.screenshot({ path: file });
  console.log("wrote", file);
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await context.addInitScript((loc) => localStorage.setItem("ma_ui_locale", loc), locale);
const page = await context.newPage();

await page.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("form input");
await page.waitForTimeout(1000);
await shot(page, "login.png");

const inputs = page.locator("form input");
await inputs.nth(0).fill(tenant);
await inputs.nth(1).fill(email);
await inputs.nth(2).fill(password);
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
  await page.goto(`${base}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1000);
  await shot(page, name);
}

await browser.close();
