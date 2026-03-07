import { test, expect } from "@playwright/test";

test.describe("Home", () => {
  test("loads and shows login or main content", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);

    // Unauthenticated users are redirected to login; wait for login page content
    await expect(
      page.getByRole("heading", { name: /welcome back/i }).or(page.getByText(/sign in to your contributr/i))
    ).toBeVisible({ timeout: 10000 });
  });
});
