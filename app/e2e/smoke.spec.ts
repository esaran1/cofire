import { expect, test } from "@playwright/test";

test("map loads and place card opens", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("map")).toBeVisible();
  const box = await page.getByTestId("map").boundingBox();
  if (!box) throw new Error("map missing");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 15_000 });
  // The shipped configuration is a transition table and a damped persistence
  // rule, neither of which has a per-feature attribution, so the Why panel is
  // absent rather than filled with invented drivers. It reappears if a model
  // that can explain itself ever ships.
  await expect(page.getByTestId("place-card")).toContainText("Dryness in");
});

test("the hindcast screen reports the look against each criterion", async ({ page }) => {
  await page.goto("/hindcast");
  await expect(page.getByText("The sealed year, opened once")).toBeVisible();
  // The look count and the criteria tally both come from artifacts; a page that
  // renders without them is showing a story rather than a result.
  await expect(page.getByText("Every criterion, as written down")).toBeVisible();
  await expect(page.getByText("Reliability broke at the longer ranges")).toBeVisible();
});

test("the about screen states where the forecasts beat their baselines", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByText("Where the forecasts beat their baselines")).toBeVisible();
  await expect(page.getByText("Where the data comes from")).toBeVisible();
});
