import { expect, test } from "@playwright/test";
import { LANGS, ROUTES } from "./routes";

/**
 * The daily smoke run (.github/workflows/smoke.yml): every route in both
 * languages loads from the static site with no page error, and the map draws
 * a Place Card from the published data, on the self-hosted basemap.
 */
for (const lang of LANGS) {
  for (const r of ROUTES) {
    test(`${r.name} (${lang}) loads cleanly`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      const res = await page.goto(`${r.path}?lang=${lang}`);
      expect(res?.status()).toBeLessThan(400);
      await expect(page.locator(r.ready).first()).toBeVisible({ timeout: 45_000 });
      await expect(page.locator("html")).toHaveAttribute("lang", /.+/);
      expect(errors, errors.join("\n")).toEqual([]);
    });
  }
}

test("the map shows a Place Card from the latest published issue", async ({ page }) => {
  const idx = await (await page.request.get("data/domains/index.json")).json();
  const latest = idx.issues[idx.issues.length - 1];
  const bundle = await (await page.request.get(`data/domains/denver/${latest}.json`)).json();
  await page.goto(`?domain=denver&cell=${bundle.cells[0].id}`);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("place-card")).toContainText(latest);
});

test("the basemap archive answers range requests", async ({ page }) => {
  const r = await page.request.get("tiles/colorado.pmtiles", { headers: { Range: "bytes=0-126" } });
  expect(r.status()).toBe(206);
  expect((await r.body()).length).toBe(127);
});

test("the open data index lists the latest issue's files", async ({ page }) => {
  const idx = await (await page.request.get("data/open/index.json")).json();
  for (const f of [idx.latest.csv, idx.latest.geojson, idx.latest.json]) {
    const r = await page.request.head(`data/open/${f}`);
    expect(r.status(), f).toBe(200);
  }
});
