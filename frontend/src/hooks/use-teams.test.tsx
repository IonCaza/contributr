import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTeams, useTeam, useTeamMembers } from "./use-teams";
import { api } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  api: {
    listTeams: vi.fn(),
    getTeam: vi.fn(),
    listTeamMembers: vi.fn(),
  },
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useTeams", () => {
  beforeEach(() => vi.mocked(api.listTeams).mockReset());

  it("returns teams on success", async () => {
    const teams = [{ id: "t1", name: "Alpha" }];
    vi.mocked(api.listTeams).mockResolvedValue(teams);

    const { result } = renderHook(() => useTeams(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(teams);
  });

  it("passes projectId to api", async () => {
    vi.mocked(api.listTeams).mockResolvedValue([]);
    const { result } = renderHook(() => useTeams("p1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listTeams).toHaveBeenCalledWith("p1");
  });

});

describe("useTeam", () => {
  beforeEach(() => vi.mocked(api.getTeam).mockReset());

  it("fetches a single team", async () => {
    vi.mocked(api.getTeam).mockResolvedValue({ id: "t1", name: "Beta" });
    const { result } = renderHook(() => useTeam("t1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ id: "t1", name: "Beta" });
  });
});

describe("useTeamMembers", () => {
  beforeEach(() => vi.mocked(api.listTeamMembers).mockReset());

  it("fetches members for a team", async () => {
    const members = [{ contributor_id: "c1", contributor_name: "Alice", role: "member" }];
    vi.mocked(api.listTeamMembers).mockResolvedValue(members);
    const { result } = renderHook(() => useTeamMembers("t1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(members);
  });
});
