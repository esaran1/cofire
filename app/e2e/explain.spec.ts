import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ExplainSchema } from "../lib/explainSchema";
import { categoryOf, decompose, frequency, liveProbability, monthOf, weeksLikeThis } from "../lib/explain";

/** v1.3 explanations: frequency framing, weeks like this one, why did this change. None writes to the database. */

const DOMAINS = ["denver", "upper_south_platte", "dillon", "larimer", "pueblo"];
const explainOf = (d: string) => ExplainSchema.parse(JSON.parse(fs.readFileSync(`../artifacts/v13/explain/${d}.json`, "utf8")));
function bundlesRoot(): string {
  for (const d of ["../artifacts/ship/domains", "../demo/artifacts/ship/domains", "public/data/domains"]) if (fs.existsSync(path.join(d, "index.json"))) return d;
  throw new Error("no bundles");
}
const readBundle = (d: string, i: string) => JSON.parse(fs.readFileSync(path.join(bundlesRoot(), d, `${i}.json`), "utf8"));

test("every frequency sentence's N matches the percentage shown beside it", async ({ page }) => {
  test.setTimeout(300_000);
  for (const d of DOMAINS) {
    await page.goto(`/?domain=${d}`);
    await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 30_000 });
    for (const h of ["2", "4", "8"]) {
      await page.getByTestId("place-card").getByRole("button", { name: `${h} weeks ahead` }).click();
      await expect(page.getByTestId("dryness-heading")).toContainText(`${h} weeks`);
      const pairs = await page.locator("[data-testid=target-probability], [data-testid=target-base-rate]").evaluateAll((rows) =>
        rows.map((r) => [r.querySelector("[data-testid=target-percent]")?.textContent ?? null, r.querySelector("[data-testid=frequency]")?.getAttribute("data-n") ?? null]),
      );
      for (const [pct, freq] of pairs) {
        if (pct === null) continue;
        expect(freq, `${d} h${h}`).toBe(pct.trim() === "<1%" ? "<1" : pct.trim().replace("%", ""));
      }
    }
  }
});

test("the weeks like this one reproduce the model's drought odds for sampled cells", () => {
  for (const d of DOMAINS) {
    const ex = explainOf(d);
    const idx = JSON.parse(fs.readFileSync(path.join(bundlesRoot(), "index.json"), "utf8"));
    const issue = idx.issues[idx.issues.length - 1];
    const b = readBundle(d, issue);
    for (const cell of b.cells.filter((_: unknown, i: number) => i % 7 === 0)) {
      for (const target of ["d_ge2_h4", "d_nochange_h2", "d_improve1_h8", "d_intensify1_h4"]) {
        const s = { issue, usdm: cell.usdm, erc_pct: cell.erc_pct };
        const cases = weeksLikeThis(ex, target, s);
        const p = liveProbability(ex, target, s, "base");
        if (!cases || p === null) continue;
        const tab = ex.drought[String(Number(target.slice(-1)))];
        const c = categoryOf(cell.usdm);
        const mask = [0, 1, 2, 3, 4].map((k) => (target.startsWith("d_ge2") ? k >= 2 : target.startsWith("d_nochange") ? k === c : target.startsWith("d_improve1") ? k <= c - 1 : k >= c + 1));
        const gEvent = tab.global_row.reduce((a, v, k) => a + (mask[k] ? v : 0), 0);
        const fromCounts = (cases.total.k + tab.prior_strength * gEvent) / (cases.total.n + tab.prior_strength);
        expect(Math.abs(fromCounts - p), `${d} ${cell.id} ${target}`).toBeLessThan(1e-9);
        expect(cases.years.every((y) => y.year >= 2007 && y.year <= 2021)).toBe(true);
      }
    }
  }
});

test("a change's parts sum to the total for every cell and target", () => {
  let checked = 0;
  for (const d of DOMAINS) {
    const ex = explainOf(d);
    const idx = JSON.parse(fs.readFileSync(path.join(bundlesRoot(), "index.json"), "utf8"));
    const [prevIssue, issue] = idx.issues.slice(-2);
    const a = readBundle(d, prevIssue);
    const b = readBundle(d, issue);
    b.targets.forEach((target: string, ti: number) => {
      const regional = b.decisions.targets[target][0] === "base_rate";
      for (const cell of b.cells) {
        const prev = a.cells.find((x: { id: string }) => x.id === cell.id);
        if (!prev || cell.p[ti] === null || prev.p[ti] === null) continue;
        const ch = decompose(ex, target, { issue: prevIssue, usdm: prev.usdm, erc_pct: prev.erc_pct }, { issue, usdm: cell.usdm, erc_pct: cell.erc_pct }, prev.p[ti], cell.p[ti], regional);
        expect(Math.abs(ch.state + ch.season + ch.method - ch.total)).toBeLessThan(1e-9);
        if (!regional && target.startsWith("d_")) expect(ch.method).toBe(0); // same method both weeks
        checked++;
      }
    });
    expect(monthOf(issue)).toBeGreaterThan(0);
  }
  expect(checked).toBeGreaterThan(1000);
});

test("the brief's frequency lines match its odds table", async ({ page }) => {
  const latest = JSON.parse(fs.readFileSync("lib/brief_latest.json", "utf8"));
  await page.goto("/brief?lang=en");
  const lines = page.getByTestId("brief-frequency").locator("li");
  await expect(lines.first()).toBeVisible({ timeout: 20_000 });
  for (const r of latest.brief.denver.rows) {
    const li = page.locator(`[data-testid=brief-frequency] li[data-cat="${r.cat}"]`);
    if (typeof r.stay === "number") await expect(li).toHaveAttribute("data-stay", String(frequency(r.stay).n));
    if (typeof r.worsen === "number") await expect(li).toHaveAttribute("data-worsen", String(frequency(r.worsen).n));
  }
  await expect(lines.first().getByRole("img")).toHaveAttribute("aria-label", /100 weeks like this one/i);
});
