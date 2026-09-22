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

/**
 * One shot per Place Card rendering state, from the real export.
 *
 * All three horizons are shot inside ONE test, deliberately. Each Playwright
 * test gets a fresh browser, and the card mounts at its default horizon; when
 * these were three separate tests every file came back byte-identical, because
 * each fresh page was captured before its chip click could matter. Driving the
 * chips within one session is also what a reader actually does.
 *
 * The map spans both counties, so each is reached by clicking its part of the
 * frame: Larimer in the north, Pueblo in the south. Both are shot because the
 * two continuous states live in different counties, Larimer h4 and h8 being the
 * only `historical_range` horizons. The filename records the state the payload
 * actually declared, so a shot cannot claim a state the export did not produce.
 */
for (const [county, fx, fy] of [["larimer", 0.45, 0.12], ["pueblo", 0.5, 0.7]] as const) {
test(`shoot every Place Card rendering state in ${county}`, async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(5000);
  const box = await page.locator('[data-testid="map"]').boundingBox();
  if (!box) throw new Error("map did not render");
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);

  const card = page.locator('[data-testid="place-card"]');
  await expect(card).toBeVisible({ timeout: 15_000 });
  // Trust the payload over the click: if the click landed in the other county,
  // the shot is named for what it actually shows.
  const shown =
    (await card.innerText()).match(/larimer|pueblo/i)?.[0]?.toLowerCase() ?? "unknown";
  expect(shown, `click at (${fx}, ${fy}) of the frame did not land in ${county}`).toBe(county);

  const seen = new Set<string>();
  for (const horizon of ["2", "4", "8"]) {
    await card.getByRole("button", { name: `${horizon}w` }).click();
    await expect(card).toContainText(`in ${horizon} weeks`, { timeout: 10_000 });
    await page.waitForTimeout(500);

    const state =
      (await card.locator('[data-testid="erc-interval"]').count()) > 0
        ? "interval"
        : (await card.locator('[data-testid="erc-historical-range"]').count()) > 0
          ? "historical-range"
          : (await card.locator('[data-testid="erc-uncalibrated"]').count()) > 0
            ? "uncalibrated"
            : "point-only";
    const buf = await card.screenshot({
      path: `${OUT}/placecard-${shown}-h${horizon}-${state}.png`,
    });
    // Three identical files would mean the chips never took effect, which is
    // exactly the failure this shape of test was written to rule out.
    const digest = createHash("md5").update(buf).digest("hex");
    expect(seen.has(digest), `h${horizon} is identical to an earlier horizon`).toBe(false);
    seen.add(digest);
  }
});
}
