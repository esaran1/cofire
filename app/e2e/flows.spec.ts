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

test("a missed refresh is shown as stale, and a current issue is not", async ({ page }) => {
  await page.goto("/brief");
  const latest = await page.getByTestId("brief-issue").locator("option").first().textContent();
  const day = (offset: number) => new Date(new Date(`${latest}T12:00:00Z`).getTime() + offset * 86_400_000);
  await page.clock.setFixedTime(day(4));
  await page.goto("/?domain=denver");
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("stale-badge")).toHaveCount(0);
  await page.clock.setFixedTime(day(19));
  await page.goto("/?domain=denver");
  await expect(page.getByTestId("stale-badge")).toContainText("19 days ago", { timeout: 20_000 });
  await page.goto("/brief");
  await expect(page.getByTestId("stale-badge")).toContainText("latest good numbers");
});

test("Ember actions link their programs, and the card links current smoke", async ({ page }) => {
  await page.goto("/ember");
  await expect(page.getByText("Everything else")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("checkbox").first()).toBeVisible({ timeout: 20_000 });
  await expect.poll(() => page.locator("a[data-link]").count()).toBeGreaterThanOrEqual(6);
  await expect(page.locator('a[data-link="air_alerts"]')).toHaveAttribute("href", "https://www.enviroflash.info/");
  await page.goto("/?domain=denver");
  await expect(page.getByTestId("smoke-link").locator("a")).toHaveAttribute("href", "https://fire.airnow.gov/", { timeout: 20_000 });
});

test("Denver's neighborhoods layer shows EnviroScreen as context, and only for Denver", async ({ page }) => {
  await page.goto("/?domain=denver");
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("layer-burden").click();
  await expect(page).toHaveURL(/layer=burden/);
  await expect(page.getByTestId("map-legend")).toContainText("context, not a forecast");
  await expect(page.getByTestId("tract-card")).toContainText("Context, not a forecast");
  const list = page.getByTestId("tract-list");
  await list.locator("summary").click();
  const first = list.getByTestId("tract-list-item").first();
  const geoid = await first.getAttribute("data-geoid");
  await first.click();
  await expect(page.getByTestId("tract-card")).toContainText(`Census tract ${geoid}`);
  await expect(page.getByTestId("tract-card").locator("[data-row]")).toHaveCount(4);
  await expect(page.getByTestId("map-announce")).toHaveText(`Showing census tract ${geoid}.`);
  // The forecast for the cell there is still on the card.
  await expect(page.getByTestId("place-card")).toBeVisible();
  await page.getByTestId("domain-switcher").selectOption("dillon");
  await expect(page.getByTestId("layer-burden")).toHaveCount(0);
  await expect(page).toHaveURL(/layer=fire/, { timeout: 20_000 });
});
