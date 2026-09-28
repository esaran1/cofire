import { expect, test } from "@playwright/test";

/** Flows between screens, and the map without a network. None writes to the database. */

test("the map draws its cells with no network for the basemap", async ({ page }) => {
  await page.route(/openstreetmap|protomaps/, (r) => r.abort("internetdisconnected"));
  for (const d of ["pueblo", "dillon"]) {
    await page.goto(`/?domain=${d}`);
    await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __cofireMap?: { querySourceFeatures: (s: string) => unknown[] } }).__cofireMap?.querySourceFeatures("cells").length ?? 0), { timeout: 15_000 })
      .toBeGreaterThan(0);
    await page.reload();
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __cofireMap?: { querySourceFeatures: (s: string) => unknown[] } }).__cofireMap?.querySourceFeatures("cells").length ?? 0), { timeout: 15_000 })
      .toBeGreaterThan(0);
  }
});

test("the Hindcast replay link opens that issue and range", async ({ page }) => {
  await page.goto("/hindcast");
  await page.getByRole("link", { name: "Replay a 2026 issue" }).click();
  await expect(page.getByTestId("place-domain")).toContainText("2026-05-05", { timeout: 20_000 });
  await expect(page.getByTestId("dryness-heading")).toContainText("2 weeks");
  await expect(page).toHaveURL(/issue=2026-05-05/);
});

test("adopting a cell survives a reload and is offered on Observe", async ({ page }) => {
  await page.goto("/?domain=denver");
  const adopt = page.getByTestId("adopt");
  await expect(adopt).toBeVisible({ timeout: 20_000 });
  if ((await adopt.innerText()) === "Adopted") await adopt.click();
  await adopt.click();
  await expect(adopt).toHaveText("Adopted");
  await expect(adopt).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByTestId("adopt")).toHaveText("Adopted", { timeout: 20_000 });
  await page.getByRole("button", { name: "Report here" }).click();
  await expect(page.getByTestId("adopted-picks")).toContainText("Denver");
});

test("Observe explains coordinates it cannot use instead of sending them", async ({ page }) => {
  let posted = false;
  await page.route("**/observations", (r) => { if (r.request().method() === "POST") posted = true; return r.fallback(); });
  await page.goto("/observe?lat=abc&lon=xyz");
  await page.getByRole("button", { name: /File|Report|Send/ }).last().click();
  await expect(page.getByText("Enter the location as decimal degrees")).toBeVisible();
  expect(posted).toBe(false);
});

test("the map keeps its state in the URL, so Back returns to it", async ({ page }) => {
  await page.goto("/?domain=dillon&horizon=8&layer=drought");
  await expect(page.getByTestId("dryness-heading")).toContainText("8 weeks", { timeout: 20_000 });
  await expect(page).toHaveURL(/layer=drought/);
  await page.getByRole("button", { name: "Predict here" }).click();
  await expect(page).toHaveURL(/\/beat/);
  await page.goBack();
  await expect(page.getByTestId("dryness-heading")).toContainText("8 weeks", { timeout: 20_000 });
  await expect(page).toHaveURL(/domain=dillon/);
});
