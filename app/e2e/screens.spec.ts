import { expect, test } from "@playwright/test";
import { createHash } from "crypto";

/**
 * Re-shoot every screen at mobile and desktop widths.
 *
 * Run deliberately, not as part of the smoke suite:
 *   npx playwright test e2e/screens.spec.ts --project=shots
 *
 * The Place Card states are shot from real cells rather than mocked, because a
 * mocked payload would prove the component renders a state and not that the
 * shipped export produces one.
 */

const OUT = "../artifacts/frontend/screens";
const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };

const ROUTES: [string, string][] = [
  ["/", "map"],
  ["/landing", "landing"],
  ["/hindcast", "hindcast"],
  ["/about", "about"],
  ["/beat", "beat"],
  ["/ember", "ember"],
  ["/observe", "observe"],
  ["/brief", "brief"],
  ["/scoreboard", "scoreboard"],
  ["/data", "data"],
];

for (const [route, name] of ROUTES) {
  for (const [label, size] of [["mobile", MOBILE], ["desktop", DESKTOP]] as const) {
    test(`shoot ${name} ${label}`, async ({ page }) => {
      await page.setViewportSize(size);
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(route === "/" ? 5000 : 1200);
      await page.screenshot({ path: `${OUT}/${name}-${label}.png`, fullPage: route !== "/" });
    });
  }
}

const DOMAINS = ["denver", "upper_south_platte", "dillon", "larimer", "pueblo"] as const;

/** The map of every area, desktop. */
for (const d of DOMAINS) {
  test(`shoot map ${d}`, async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto(`/?domain=${d}`);
    await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/map-${d}-desktop.png` });
  });
}

/**
 * The Place Card of every area at every horizon, from the real export.
 *
 * All three horizons are shot inside ONE test: the card mounts at its default
 * horizon, and separate tests came back byte-identical because each fresh page
 * was captured before its chip click could matter. The filename records the
 * state the payload declared, so a shot cannot claim a state the export did
 * not produce.
 */
for (const d of DOMAINS) {
  test(`shoot every Place Card state in ${d}`, async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto(`/?domain=${d}`);
    const card = page.locator('[data-testid="place-card"]');
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("place-domain")).toBeVisible();

    const seen = new Set<string>();
    for (const horizon of ["2", "4", "8"]) {
      await card.getByRole("button", { name: `${horizon} weeks ahead` }).click();
      await expect(card).toContainText(`in ${horizon} weeks`, { timeout: 10_000 });
      await page.waitForTimeout(500);
      const state =
        (await card.locator('[data-testid="erc-interval"]').count()) > 0
          ? "interval"
          : (await card.locator('[data-testid="erc-uncalibrated"]').count()) > 0
            ? "uncalibrated"
            : "point-only";
      const buf = await card.screenshot({ path: `${OUT}/placecard-${d}-h${horizon}-${state}.png` });
      const digest = createHash("md5").update(buf).digest("hex");
      expect(seen.has(digest), `h${horizon} is identical to an earlier horizon`).toBe(false);
      seen.add(digest);
    }
    if (d === "denver") {
      const panel = page.getByTestId("watershed-panel");
      await panel.scrollIntoViewIfNeeded();
      await panel.screenshot({ path: `${OUT}/placecard-denver-watersheds.png` });
    }
  });
}
