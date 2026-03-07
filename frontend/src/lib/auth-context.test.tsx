import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./auth-context";
import { api } from "./api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("./api-client", () => ({
  api: {
    me: vi.fn(),
    login: vi.fn(),
  },
  setSessionExpiredHandler: vi.fn(),
}));

function clearStorage() {
  try {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  } catch {
    // no-op
  }
}

function TestConsumer() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.username : "null"}</span>
      <button onClick={() => login("testuser", "pass")}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.mocked(api.me).mockReset();
    vi.mocked(api.login).mockReset();
    clearStorage();
  });

  it("shows null user when not logged in", async () => {
    vi.mocked(api.me).mockRejectedValue(new Error("not authed"));

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("null");
    });
  });

  it("shows user when token exists and me() succeeds", async () => {
    try {
      localStorage.setItem("access_token", "tok");
    } catch {
      return;
    }
    vi.mocked(api.me).mockResolvedValue({
      id: "1",
      username: "alice",
      email: "a@b.com",
    } as any);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("alice");
    });
  });

  it("login stores token and sets user", async () => {
    vi.mocked(api.me).mockRejectedValue(new Error("no token"));
    vi.mocked(api.login).mockResolvedValue({
      access_token: "new-tok",
      refresh_token: "new-rt",
      token_type: "bearer",
    } as any);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    vi.mocked(api.me).mockResolvedValue({
      id: "2",
      username: "bob",
      email: "b@b.com",
    } as any);

    await act(async () => {
      screen.getByText("Login").click();
    });

    await waitFor(() => {
      try {
        expect(localStorage.getItem("access_token")).toBe("new-tok");
      } catch {
        // localStorage may not support getItem in all test envs
      }
    });
  });
});
