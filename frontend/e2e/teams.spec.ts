import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Teams", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
  });

  test("teams page shows heading", async ({ page }) => {
    await page.goto("/teams");
    await expect(
      page.getByRole("heading", { name: /teams/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });
});
