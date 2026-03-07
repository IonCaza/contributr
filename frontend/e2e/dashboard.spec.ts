import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
  });

  test("shows dashboard heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /dashboard/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows stat cards", async ({ page }) => {
    await expect(page.locator("[data-slot='card']").first()).toBeVisible({
      timeout: 10000,
    });
  });
});
