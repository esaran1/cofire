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

test("when the model's drought odds were not all checked, the call shows without a chance", async ({ page }) => {
  await page.route("**/predictions", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e", issue: "2026-09-22",
        locked_model: { point: 47, state: "uncalibrated", drought_now: 2, drought_likely: 2, drought_likely_p: null,
          drought_note: "some of the model's drought odds here could not be checked, so its chance is not shown" },
      }),
    });
  });
  await page.goto("/beat?domain=larimer");
  const lock = page.getByRole("button", { name: /Lock my pick|Lock another/ });
  await expect(lock).toBeEnabled({ timeout: 20_000 });
  await lock.click();
  const reveal = page.getByText("The model said").locator("..");
  await expect(reveal).toContainText("D2");
  await expect(reveal).toContainText("could not be checked");
  await expect(reveal).not.toContainText("% chance");
  await expect(reveal).toContainText("47");
  await expect(reveal).not.toContainText("n/a");
});

test("the reveal compares the locked pick with the model, and flags an unlocked change", async ({ page }) => {
  await page.route("**/predictions", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: "e2e", issue: "2026-09-22",
        locked_model: { point: 84, state: "uncalibrated", drought_now: 3, drought_likely: 3, drought_likely_p: 0.7 } }),
    });
  });
  await page.goto("/beat?domain=denver");
  await page.getByRole("radio", { name: /^D3/ }).first().click();
  await page.getByRole("radio", { name: /^Moderate/ }).first().click();
  const lock = page.getByRole("button", { name: /Lock my pick|Lock another/ });
  await expect(lock).toBeEnabled({ timeout: 20_000 });
  await lock.click();
  // Dryness 84 is in the High band (80 to 90).
  await expect(page.getByTestId("reveal-fire")).toContainText("High");
  await expect(page.getByTestId("compare-drought")).toHaveText("You: D3. Same as the model.");
  await expect(page.getByTestId("compare-fire")).toHaveText("You: Moderate. Different from the model.");
  await expect(page.getByTestId("pick-changed")).toHaveCount(0);
  await page.getByRole("radio", { name: /^D1/ }).first().click();
  await expect(page.getByTestId("pick-changed")).toBeVisible();
  await expect(page.getByTestId("compare-drought")).toHaveText("You: D3. Same as the model.");
});

test("too many picks in a minute gets a plain message", async ({ page }) => {
  await page.route("**/predictions", (route) =>
    route.request().method() === "POST" ? route.fulfill({ status: 429, body: '{"detail":"rate limit"}' }) : route.fallback());
  await page.goto("/beat?domain=denver");
  const lock = page.getByRole("button", { name: /Lock my pick|Lock another/ });
  await expect(lock).toBeEnabled({ timeout: 20_000 });
  await lock.click();
  await expect(page.getByText("That is a lot in one minute")).toBeVisible();
});
