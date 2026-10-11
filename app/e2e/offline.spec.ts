import { expect, test } from "@playwright/test";

/**
 * Offline viewing needs the service worker, which only a production build
 * registers. Run against one: PROD_BASE=http://127.0.0.1:3100 npx playwright test e2e/offline.spec.ts
 */
const BASE = process.env.PROD_BASE;
test.skip(!BASE, "needs a production build (PROD_BASE)");

test("the newest forecast and brief stay readable offline, and the page says so", async ({ page, context }) => {
  await page.goto(`${BASE}/?domain=denver`);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 30_000 });
  await page.waitForFunction(() => navigator.serviceWorker?.controller != null, null, { timeout: 30_000 }).catch(async () => {
    await page.reload();
    await page.waitForFunction(() => navigator.serviceWorker?.controller != null, null, { timeout: 30_000 });
  });
  await page.goto(`${BASE}/?domain=denver`);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 30_000 });
  await page.goto(`${BASE}/brief`);
  await expect(page.getByTestId("brief-en")).toBeVisible({ timeout: 30_000 });

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByTestId("brief-en")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("offline-banner")).toBeVisible();
  await page.goto(`${BASE}/?domain=denver`);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("offline-banner")).toBeVisible();
  await context.setOffline(false);
});
