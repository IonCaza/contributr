import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Projects", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
  });

  test("projects page shows heading and new project action", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: /new project/i })).toBeVisible();
  });
});
