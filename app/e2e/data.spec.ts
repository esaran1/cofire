import { expect, test } from "@playwright/test";

/**
 * The open data page (app/app/data/page.tsx): its dictionary lists exactly the
 * fields in the index the files are built with (cofire/v13/open_data.py), the
 * downloads point at those files, and it reads in Spanish too.
 */
test("the data dictionary matches the open data index, in both languages", async ({ page }) => {
  await page.goto("/data");
  await expect(page.getByTestId("data-title")).toHaveText("Open data");
  await expect(page.getByTestId("data-dictionary")).toBeVisible({ timeout: 30_000 });
  const fields = await page.locator("[data-field]").evaluateAll((els) => els.map((e) => e.getAttribute("data-field")));
  const href = await page.getByTestId("data-endpoint").locator("a").getAttribute("href");
  expect(href).toMatch(/\/open\/index\.json$/);
  const idx = await (await page.request.get(href as string)).json();
  expect(fields).toEqual(idx.fields.map((f: { name: string }) => f.name));
  expect(fields).toEqual(["issue", "vintage", "area", "cell", "lat", "lon", "target", "horizon_weeks", "probability", "state", "reason"]);
  // The latest issue's three files, and one pair per issue.
  for (const name of [idx.latest.csv, idx.latest.geojson, idx.latest.json]) await expect(page.locator(`[data-file="${name}"]`)).toHaveCount(1);
  await expect(page.locator("[data-issue]")).toHaveCount(idx.issues.length);
  const csv = await page.request.get((await page.locator(`[data-file="${idx.latest.csv}"]`).getAttribute("href")) as string);
  expect((await csv.text()).split("\n")[0]).toBe(fields.join(","));
  await expect(page.getByTestId("data-upstream")).toContainText("gridMET");

  await page.getByRole("button", { name: "Español" }).click();
  await expect(page.getByTestId("data-title")).toHaveText("Datos abiertos");
  await expect(page.locator('[data-field="vintage"] td').nth(2)).toContainText("Cuándo se descargaron");
});
