import { expect, test } from "@playwright/test";

test("map loads and place card opens", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("map")).toBeVisible();
  const box = await page.getByTestId("map").boundingBox();
  if (!box) throw new Error("map missing");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("why-panel")).toBeVisible();
});
