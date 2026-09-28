import { expect, test } from "@playwright/test";

/**
 * The reveal after locking a pick shows the model's numbers, not "n/a".
 *
 * It showed "n/a" twice: first because it read fields the retired v0.6 export
 * produced, then because the response schema dropped the new drought fields.
 * The lock is answered with the API's real response shape, so this checks the
 * page's parsing and rendering without writing a pick to the database.
 */
test("a locked pick reveals the model's drought category and dryness", async ({ page }) => {
  await page.route("**/predictions", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e",
        issue: "2026-09-22",
        locked_model: {
          point: 45.2, state: "uncalibrated", reason: "No band.", hist_lo: 30.9, hist_hi: 74.9,
          hist_years: "2007 to 2021", target_week: "2026-10-20",
          drought_now: 2, drought_likely: 2, drought_likely_p: 0.4756,
        },
      }),
    });
  });
  await page.goto("/beat?domain=denver");
  const lock = page.getByRole("button", { name: /Lock my pick|Lock another/ });
  await expect(lock).toBeEnabled({ timeout: 20_000 });
  await lock.click();
  const reveal = page.getByText("The model said").locator("..");
  await expect(reveal).toContainText("D2");
  await expect(reveal).toContainText("48% chance");
  await expect(reveal).toContainText("45");
  await expect(reveal).not.toContainText("n/a");
});

test("when a drought outcome was not checked, the reveal says so instead of a number", async ({ page }) => {
  await page.route("**/predictions", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e", issue: "2026-09-22",
        locked_model: { point: 47, state: "uncalibrated", drought_now: 2, drought_likely: null, drought_likely_p: null,
          drought_note: "not every drought outcome could be checked here" },
      }),
    });
  });
  await page.goto("/beat?domain=larimer");
  const lock = page.getByRole("button", { name: /Lock my pick|Lock another/ });
  await expect(lock).toBeEnabled({ timeout: 20_000 });
  await lock.click();
  const reveal = page.getByText("The model said").locator("..");
  await expect(reveal).toContainText("not shown");
  await expect(reveal).toContainText("could be checked here");
  await expect(reveal).toContainText("47");
  await expect(reveal).not.toContainText("n/a");
});
