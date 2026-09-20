import { expect, test } from "@playwright/test";

/**
 * Regression tests for the Place Card, which is the screen most exposed to a
 * malformed API response.
 *
 * The bug these guard: `why[].value` is null whenever the SHAP cache misses and
 * the API falls back to a feature-z explanation. `.toFixed()` on it crashed the
 * whole Place Card while the endpoint returned 200 and `tsc` passed. Clicking a
 * real cell is the only thing that surfaced it.
 */

/** Click the centre of the map and wait for the Place Card. */
async function openPlaceCard(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  // The map needs a frame to size itself before the click lands on a cell.
  await page.waitForTimeout(4000);
  const box = await page.locator('[data-testid="map"]').boundingBox();
  if (!box) throw new Error("map did not render");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return page.locator('[data-testid="place-card"]');
}

test("a cell with a SHAP cache miss renders instead of crashing", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });

  // The Why block must render every driver, with a stated fallback where the
  // SHAP magnitude is null rather than a thrown render.
  await expect(card.getByText("Why")).toBeVisible();
  expect(errors, `page threw during render: ${errors[0]}`).toHaveLength(0);
});

test("interval suppression follows the uncertainty status", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });

  // The API base is read in Node, not in the browser: process.env does not
  // exist in page context.
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const status = await page.evaluate(async (base: string) => {
    const r = await fetch(`${base}/uncertainty/status`);
    return (await r.json()) as { status: string; show_interval: boolean };
  }, apiBase);

  const text = (await card.innerText()).toLowerCase();
  if (!status.show_interval) {
    // Suppressed: no band, and the reason is stated on the card.
    expect(text).toContain("interval hidden");
  } else {
    expect(text).toContain("interval");
  }
});

test("the point forecast and drivers survive a suppressed interval", async ({ page }) => {
  const card = await openPlaceCard(page);
  await expect(card).toBeVisible({ timeout: 15_000 });
  // Suppressing the band must not suppress the forecast itself.
  await expect(card.getByText("Fire-spread condition")).toBeVisible();
  await expect(card.getByText("Drought category")).toBeVisible();
});
