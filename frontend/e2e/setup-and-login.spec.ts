import { test, expect } from "@playwright/test";
import { loginViaUI } from "./helpers/login";

test.describe("Setup and Login", () => {
  test("can register or skip then login via UI", async ({ page }) => {
    await loginViaUI(page);
    await expect(
      page.getByRole("heading", { name: /dashboard/i })
    ).toBeVisible({ timeout: 10000 });
  });
});
