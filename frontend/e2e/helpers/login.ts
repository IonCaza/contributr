import { type Page, expect } from "@playwright/test";

const API_BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = `${API_BASE.replace(/:3000$/, ":8000")}/api`;

const E2E_USER = {
  username: process.env.E2E_USERNAME ?? "e2e-testuser",
  password: process.env.E2E_PASSWORD ?? "e2e-testpass123",
  email: "e2e-test@contributr.local",
  full_name: "E2E Test User",
};

/**
 * Ensure a test user exists (register if possible, ignore 403).
 * Then log in via the UI and wait for the dashboard.
 */
export async function loginViaUI(page: Page) {
  // Try to seed the user via API (first-user bootstrap).
  const ctx = page.request;
  try {
    await ctx.post(`${API}/auth/register`, {
      data: {
        username: E2E_USER.username,
        password: E2E_USER.password,
        email: E2E_USER.email,
        full_name: E2E_USER.full_name,
      },
    });
  } catch {
    // Registration may be closed or user already exists — that's fine.
  }

  await page.goto("/login");
  await page.getByLabel(/username/i).fill(E2E_USER.username);
  await page.getByLabel(/password/i).fill(E2E_USER.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

export { E2E_USER };
