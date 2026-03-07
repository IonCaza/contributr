import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Settings", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
  });

  test("settings page loads", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: /settings/i }).first()).toBeVisible({ timeout: 10000 });
  });
});
