import { expect, test } from "@playwright/test";

const tenant = process.env.E2E_TENANT || "demo";
const email = process.env.E2E_EMAIL || "admin@example.com";
const password = process.env.E2E_PASSWORD || "DemoPass123!";

test.describe("MailArchive smoke", () => {
  test("login page loads branding and form", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Email")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByLabel("Contraseña")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
    // Brand logo (img alt) on first paint
    await expect(page.getByAltText("MailArchive")).toBeVisible();
  });

  test("API health via UI origin proxy or direct", async ({ request }) => {
    const apiBase = process.env.E2E_API_URL || "http://127.0.0.1:18100";
    const res = await request.get(`${apiBase}/health`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("login with real demo credentials reaches app", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Email")).toBeVisible({ timeout: 30_000 });
    const tenantField = page.getByLabel("Tenant");
    if (await tenantField.isVisible().catch(() => false)) {
      await tenantField.fill(tenant);
    }
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill(password);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/app/, { timeout: 30_000 });
  });
});
