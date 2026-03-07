import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRepo, useRepoStats, useRepoBranches } from "./use-repos";
import { api } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  api: {
    getRepo: vi.fn(),
    getRepoStats: vi.fn(),
    listBranches: vi.fn(),
  },
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useRepo", () => {
  beforeEach(() => vi.mocked(api.getRepo).mockReset());

  it("fetches repo detail", async () => {
    vi.mocked(api.getRepo).mockResolvedValue({ id: "r1", name: "my-repo" });
    const { result } = renderHook(() => useRepo("r1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ id: "r1", name: "my-repo" });
  });

});

describe("useRepoStats", () => {
  beforeEach(() => vi.mocked(api.getRepoStats).mockReset());

  it("fetches repo stats", async () => {
    const stats = { total_commits: 42, total_lines_added: 1000 };
    vi.mocked(api.getRepoStats).mockResolvedValue(stats);
    const { result } = renderHook(() => useRepoStats("r1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(stats);
  });
});

describe("useRepoBranches", () => {
  beforeEach(() => vi.mocked(api.listBranches).mockReset());

  it("fetches branches for a repo", async () => {
    const branches = [{ name: "main" }, { name: "dev" }];
    vi.mocked(api.listBranches).mockResolvedValue(branches);
    const { result } = renderHook(() => useRepoBranches("r1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(branches);
  });
});
