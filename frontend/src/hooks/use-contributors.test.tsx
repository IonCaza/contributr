import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useContributors, useDuplicateContributors, useContributor } from "./use-contributors";
import { api } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  api: {
    listContributors: vi.fn(),
    getDuplicateContributors: vi.fn(),
    getContributor: vi.fn(),
  },
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useContributors", () => {
  beforeEach(() => vi.mocked(api.listContributors).mockReset());

  it("returns contributors on success", async () => {
    const data = [{ id: "c1", canonical_name: "Alice" }];
    vi.mocked(api.listContributors).mockResolvedValue(data);

    const { result } = renderHook(() => useContributors(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(data);
  });

  it("filters by projectId", async () => {
    vi.mocked(api.listContributors).mockResolvedValue([]);
    const { result } = renderHook(() => useContributors("p1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listContributors).toHaveBeenCalledWith("p1");
  });

});

describe("useDuplicateContributors", () => {
  beforeEach(() => vi.mocked(api.getDuplicateContributors).mockReset());

  it("fetches duplicate groups", async () => {
    const dupes = [{ group_key: "email:alice", contributor_ids: ["c1", "c2"] }];
    vi.mocked(api.getDuplicateContributors).mockResolvedValue(dupes);
    const { result } = renderHook(() => useDuplicateContributors(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(dupes);
  });
});

describe("useContributor", () => {
  beforeEach(() => vi.mocked(api.getContributor).mockReset());

  it("fetches a single contributor", async () => {
    vi.mocked(api.getContributor).mockResolvedValue({ id: "c1", canonical_name: "Bob" });
    const { result } = renderHook(() => useContributor("c1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.canonical_name).toBe("Bob");
  });
});
