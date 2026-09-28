import { expect, test, type Page } from "@playwright/test";

/**
 * Every route, every domain. Denver is the default because it is the district
 * being judged; the watersheds are where its water comes from.
 */
const DOMAINS = [
  { id: "denver", label: "Denver", area: "city", validation: true },
  { id: "upper_south_platte", label: "Upper South Platte", area: "watershed", validation: true },
  { id: "dillon", label: "Dillon", area: "watershed", validation: true },
  { id: "larimer", label: "Larimer", area: "county", validation: false },
  { id: "pueblo", label: "Pueblo", area: "county", validation: false },
];

const ROUTES = ["/", "/beat", "/observe", "/ember", "/hindcast", "/about", "/landing"];

async function noCrash(page: Page) {
  await expect(page.getByText("Something went wrong")).toHaveCount(0);
  await expect(page.getByText("Application error")).toHaveCount(0);
  await expect(page.getByText("could not be shown")).toHaveCount(0);
}

test("the map opens on Denver by default", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("map-title")).toHaveText("Denver", { timeout: 20_000 });
  await expect(page.getByTestId("domain-switcher")).toHaveValue("denver");
});

for (const d of DOMAINS) {
  test(`${d.id}: the Place Card opens with its own area`, async ({ page }) => {
    await page.goto(`/?domain=${d.id}`);
    await expect(page.getByTestId("map-title")).toHaveText(d.label, { timeout: 20_000 });
    const card = page.getByTestId("place-card");
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("place-domain")).toContainText(d.label);
    await expect(card).toContainText("Dryness in");
    await expect(page.getByTestId("erc-history")).toBeVisible();
    // No band anywhere: the point forecast and the labelled history only.
    await expect(page.getByTestId("erc-interval")).toHaveCount(0);
    await expect(page.getByTestId("validation-note")).toHaveCount(d.validation ? 1 : 0);
    await noCrash(page);
  });

  for (const route of ROUTES) {
    test(`${d.id}: ${route} renders`, async ({ page }) => {
      await page.goto(`${route}?domain=${d.id}`);
      await expect(page.getByTestId("domain-switcher")).toHaveValue(d.id, { timeout: 20_000 });
      await noCrash(page);
      if (route === "/ember") {
        await expect(page.getByTestId("ember-title")).toHaveText(
          d.id === "denver" ? "Urban Ember Score" : "Ember Score",
          { timeout: 20_000 },
        );
      }
      if (route === "/hindcast") {
        await expect(page.getByTestId("hindcast-domain-note")).toHaveCount(d.validation ? 1 : 0);
      }
    });
  }
}

test("the Denver card carries the watersheds its water comes from", async ({ page }) => {
  await page.goto("/?domain=denver");
  const panel = page.getByTestId("watershed-panel");
  await expect(panel).toBeVisible({ timeout: 20_000 });
  await expect(panel).toContainText("Where Denver's water comes from");
  await expect(page.getByTestId("watershed-upper_south_platte")).toContainText("Upper South Platte");
  await expect(page.getByTestId("watershed-dillon")).toContainText("Dillon");
  await expect(panel).toContainText("Strontia Springs");
  // Denver's own ERC targets are named as relative dryness, not fire danger.
  await expect(page.getByTestId("place-card")).toContainText("Drier than 90% of past weeks here");
});

test("a watershed card has no watershed panel of its own", async ({ page }) => {
  await page.goto("/?domain=upper_south_platte");
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("watershed-panel")).toHaveCount(0);
  await expect(page.getByTestId("place-card")).toContainText("Fire-spread conditions above the 90th percentile");
});

test("a target that cannot be checked shows the base rate and says why", async ({ page }) => {
  // Dillon: drought reaching D2 did not happen in 2022 or 2023 validation.
  await page.goto("/?domain=dillon");
  const card = page.getByTestId("place-card");
  await expect(card).toBeVisible({ timeout: 20_000 });
  const base = page.getByTestId("target-base-rate").filter({ hasText: "Drought reaching D2 or worse" });
  await expect(base).toHaveCount(1);
  await expect(base).toContainText(/usual rate for cells in (D\d|no drought or D0) here/);
  await base.getByRole("button").first().click();
  await expect(base).toContainText("did not happen in this area in 2022 or 2023");
});

test("switching the area moves the map and the card", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("map-title")).toHaveText("Denver", { timeout: 20_000 });
  await page.getByTestId("domain-switcher").selectOption("dillon");
  await expect(page.getByTestId("map-title")).toHaveText("Dillon");
  await expect(page.getByTestId("place-domain")).toContainText("Dillon", { timeout: 20_000 });
  await expect(page).toHaveURL(/domain=dillon/);
});
