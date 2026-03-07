import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useProjects } from "./use-projects";
import { api } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  api: {
    listProjects: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

describe("useProjects", () => {
  beforeEach(() => {
    vi.mocked(api.listProjects).mockReset();
  });

  it("returns loading then data when api.listProjects resolves", async () => {
    const projects = [
      {
        id: "id-1",
        name: "Project One",
        description: "First project",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ];
    vi.mocked(api.listProjects).mockResolvedValue(projects);

    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(projects);
    expect(api.listProjects).toHaveBeenCalledTimes(1);
  });

  it("returns error when api.listProjects rejects", async () => {
    vi.mocked(api.listProjects).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});
