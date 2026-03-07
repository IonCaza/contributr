import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Auth", () => {
  test("login with valid credentials redirects to dashboard", async ({ page }) => {
    await loginViaUI(page);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10000 });
  });
});
