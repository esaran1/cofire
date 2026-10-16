import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { LANGS, ROUTES } from "./routes";

/**
 * Accessibility: every route in both languages, checked with axe against
 * WCAG 2.1 A and AA. Serious and critical violations fail; the rest are
 * reported in the test output.
 */
for (const lang of LANGS) {
  for (const r of ROUTES) {
    test(`${r.name} (${lang}) has no serious or critical axe violations`, async ({ page }, info) => {
      await page.goto(`${r.path}?lang=${lang}`);
      await expect(page.locator(r.ready).first()).toBeVisible({ timeout: 45_000 });
      await page.waitForLoadState("networkidle");
      // Check the settled page, not a fade caught halfway: wait for every finite animation to end.
      await page.evaluate(() => Promise.all(document.getAnimations().filter((a) => Number.isFinite(a.effect?.getComputedTiming().endTime ?? Infinity)).map((a) => a.finished.catch(() => undefined))));
      await page.waitForTimeout(600);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      const minor = result.violations.filter((v) => !bad.includes(v));
      if (minor.length) info.annotations.push({ type: "axe-minor", description: minor.map((v) => `${v.id} (${v.impact}, ${v.nodes.length})`).join("; ") });
      expect(bad.map((v) => `${v.id} [${v.impact}] ${v.help}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  }
}
