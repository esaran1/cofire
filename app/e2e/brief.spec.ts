import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { buildBrief } from "../lib/brief";
import { LINKS } from "../lib/links";
import type { Bundle } from "../lib/schemas";

/** The weekly brief: its numbers are the bundles' numbers, and the page shows them. None writes to the database. */

function root(): string {
  for (const d of ["../artifacts/ship/domains", "../demo/artifacts/ship/domains", "public/data/domains"]) {
    if (fs.existsSync(path.join(d, "index.json"))) return d;
  }
  throw new Error("no bundles found");
}
const read = (d: string, i: string) => JSON.parse(fs.readFileSync(path.join(root(), d, `${i}.json`), "utf8")) as Bundle;

test("every brief number is a bundle value, a cell count or a difference", () => {
  const issues: string[] = JSON.parse(fs.readFileSync(path.join(root(), "index.json"), "utf8")).issues;
  const [prev, cur] = issues.slice(-2);
  const den = read("denver", cur);
  const usp = read("upper_south_platte", cur);
  const b = buildBrief(den, [{ id: "upper_south_platte", label: "Upper South Platte", bundle: usp }], read("denver", prev), {
    upper_south_platte: read("upper_south_platte", prev),
  });
  expect(b.issue).toBe(cur);
  expect(b.prevIssue).toBe(prev);
  expect(b.denver.rows.reduce((s, r) => s + r.cells, 0)).toBe(den.cells.filter((c) => c.usdm !== null).length);
  for (const r of b.denver.rows) {
    const cell = den.cells.find((c) => c.usdm !== null && Math.round(c.usdm as number) === r.cat)!;
    const p = (t: string) => cell.p[den.targets.indexOf(`${t}_h4`)] ?? null;
    // Each row's odds are exactly what every cell in that category carries,
    // including null where the target did not pass its check.
    for (const c of den.cells.filter((x) => x.usdm !== null && Math.round(x.usdm as number) === r.cat)) {
      expect(c.p[den.targets.indexOf("d_nochange_h4")] ?? null).toBe(p("d_nochange"));
    }
    expect(r.stay).toBe(p("d_nochange"));
    expect(r.ease).toBe(r.cat === 0 ? "impossible" : p("d_improve1"));
    expect(r.worsen).toBe(r.cat === 4 ? "impossible" : p("d_intensify1"));
  }
  expect(b.water[0].f80?.mean).toBe((usp.summary["4"] as Record<string, { mean: number }>).f_gt80_h4.mean);
  expect(b.denver.dryNow).toBe(den.summary.erc_pct_now_median);
});

test("the brief page shows this week, compares last week, and links only checked sources", async ({ page }) => {
  await page.goto("/brief?lang=en");
  await expect(page.getByTestId("brief-en")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("brief-drought-now")).toContainText("Denver cells are in");
  await expect(page.getByTestId("brief-fire").locator("tr[data-area]")).toHaveCount(3);
  await expect(page.getByTestId("brief-changes").locator("li").first()).toBeVisible();
  await expect(page.getByTestId("brief-actions").locator("li")).toHaveCount(3);
  const known = new Set(Object.values(LINKS).map((l) => l.url));
  for (const href of await page.locator("[data-testid=brief-en] a").evaluateAll((as) => as.map((a) => a.getAttribute("href")))) {
    expect(known.has(href as string), href as string).toBe(true);
  }
  // Another week: the URL follows, and the dates change.
  const sel = page.getByTestId("brief-issue");
  const options = await sel.locator("option").allTextContents();
  await sel.selectOption(options[3]);
  await expect(page).toHaveURL(new RegExp(`issue=${options[3]}`));
  await page.getByTestId("lang-es").click();
  await expect(page.getByTestId("brief-title")).toHaveText("Resumen semanal de sequía e incendios para Denver");
  await expect(page.getByTestId("brief-es")).not.toContainText("Denver cells are in");
});
