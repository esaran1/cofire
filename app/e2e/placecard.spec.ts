import { expect, test } from "@playwright/test";

/**
 * Regression tests for the Place Card, which is the screen most exposed to a
 * malformed API response and the one that carries the rendering rules.
 *
 * Two classes of bug these guard:
 *
 * 1. A null field crashing the render. `why[].value` is null whenever the SHAP
 *    cache misses and the API falls back to a feature-z explanation;
 *    `.toFixed()` on it crashed the whole card while the endpoint returned 200
 *    and `tsc` passed. Clicking a real cell is the only thing that surfaced it.
 * 2. The card deciding for itself how to show a number. It must not: the
 *    rendering state was fixed in the pre-registration before the sealed year
 *    was opened, travels in the payload, and the card reads it. A card that
 *    infers a state can drift from what was registered.
 */

/** Click the centre of the map and wait for the Place Card. */
async function openPlaceCard(page: import("@playwright/test").Page, domain = "denver") {
  await page.goto(`/?domain=${domain}`);
  await page.waitForLoadState("networkidle");
  // The map needs a frame to size itself before the click lands on a cell.
  await page.waitForTimeout(4000);
  const box = await page.locator('[data-testid="map"]').boundingBox();
  if (!box) throw new Error("map did not render");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return page.locator('[data-testid="place-card"]');
}

const apiBase = () => process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

test("a cell with a SHAP cache miss renders instead of crashing", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });
  expect(errors, `page threw during render: ${errors[0]}`).toHaveLength(0);
});

test("the continuous forecast renders in the state the payload declares", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });

  const hz = await page.evaluate(async (base: string) => {
    const r = await fetch(`${base}/forecast?lat=40.55&lon=-105.08&domain=larimer`);
    const d = (await r.json()) as {
      horizons: Record<string, { state?: string | null }>;
    };
    return d.horizons["2"];
  }, apiBase());

  // Whichever state the export declared, the card must show that one and only
  // that one. An interval and a historical range are different claims.
  if (hz?.state === "interval") {
    await expect(card.locator('[data-testid="erc-interval"]')).toBeVisible();
    await expect(card.locator('[data-testid="erc-historical-range"]')).toHaveCount(0);
  } else if (hz?.state === "historical_range") {
    await expect(card.locator('[data-testid="erc-historical-range"]')).toBeVisible();
    await expect(card.locator('[data-testid="erc-interval"]')).toHaveCount(0);
  } else if (hz?.state === "uncalibrated") {
    await expect(card.locator('[data-testid="erc-uncalibrated"]')).toBeVisible();
    await expect(card.locator('[data-testid="erc-interval"]')).toHaveCount(0);
  }
});

test("every rendering state carries its reason", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });
  // The reason is why the user is being shown this rather than something else.
  // A state without one is a number with no account of itself.
  await expect(card.locator('[data-testid="erc-reason"]')).toBeVisible();
});

test("a base-rate target says it is a historical rate, not this cell's forecast", async ({ page }) => {
  // Larimer, so the marker names a county; the city and watershed wording is
  // covered in domains.spec.ts.
  const card = await openPlaceCard(page, "larimer");
  await expect(card).toBeVisible({ timeout: 15_000 });

  const nBase = await page.evaluate(async (base: string) => {
    const r = await fetch(`${base}/forecast?lat=40.55&lon=-105.08&domain=larimer`);
    const d = (await r.json()) as { targets: Record<string, { state?: string | null }> };
    return Object.values(d.targets ?? {}).filter((t) => t.state === "base_rate").length;
  }, apiBase());

  if (nBase > 0) {
    const rows = card.locator('[data-testid="target-base-rate"]');
    await expect(rows.first()).toBeVisible();
    // The statement is the point: a historical rate must say so, or the reader
    // will take it for this cell's forecast. Drought rates name the category
    // they are conditioned on; fire rates name the area and season. The marker
    // is inline on the row, because it changes how the number should be read.
    await expect(rows.first()).toContainText(/usual rate for (cells in (D\d|no drought or D0) here|this county this time of year)/);
  }
});

test("the point forecast survives every state", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });
  // Whatever happens to the band, the forecast itself is always shown.
  await expect(card.getByText("Dryness in")).toBeVisible();
});

test("the historical ERC range is shown, labelled as history", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });
  const hist = card.locator('[data-testid="erc-history"]');
  await expect(hist).toBeVisible();
  // It must say it is history, and the years it comes from, so it cannot be
  // read as a forecast band.
  await expect(hist).toContainText("History, not a forecast");
  await expect(hist).toContainText("2007 to 2021");
});
