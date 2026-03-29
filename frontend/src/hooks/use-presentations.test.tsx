import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePresentations, usePresentation, usePresentationTemplate } from "./use-presentations";
import { api } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  api: {
    listPresentations: vi.fn(),
    getPresentation: vi.fn(),
    getPresentationTemplate: vi.fn(),
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

describe("usePresentations", () => {
  beforeEach(() => {
    vi.mocked(api.listPresentations).mockReset();
  });

  it("returns loading then data", async () => {
    const items = [
      {
        id: "p-1",
        title: "Sprint Dashboard",
        description: "Sprint 23 metrics",
        prompt: "Create a sprint dashboard",
        status: "draft",
        template_version: 1,
        created_at: "2026-03-27T00:00:00Z",
        updated_at: null,
      },
    ];
    vi.mocked(api.listPresentations).mockResolvedValue(items);

    const { result } = renderHook(() => usePresentations("project-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(items);
    expect(api.listPresentations).toHaveBeenCalledWith("project-1");
  });
});

describe("usePresentation", () => {
  beforeEach(() => {
    vi.mocked(api.getPresentation).mockReset();
  });

  it("fetches a single presentation", async () => {
    const pres = {
      id: "p-1",
      project_id: "project-1",
      title: "Sprint Dashboard",
      description: null,
      component_code: "function App() {}",
      template_version: 1,
      prompt: "Create a sprint dashboard",
      chat_session_id: null,
      created_by_id: "user-1",
      status: "draft",
      created_at: "2026-03-27T00:00:00Z",
      updated_at: null,
    };
    vi.mocked(api.getPresentation).mockResolvedValue(pres);

    const { result } = renderHook(
      () => usePresentation("project-1", "p-1"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(pres);
    expect(api.getPresentation).toHaveBeenCalledWith("project-1", "p-1");
  });
});

describe("usePresentationTemplate", () => {
  beforeEach(() => {
    vi.mocked(api.getPresentationTemplate).mockReset();
  });

  it("fetches template by version with infinite cache", async () => {
    const tmpl = {
      id: "t-1",
      version: 1,
      template_html: "<html>/* __COMPONENT_CODE__ */</html>",
      description: "Initial v1",
      created_at: "2026-03-27T00:00:00Z",
    };
    vi.mocked(api.getPresentationTemplate).mockResolvedValue(tmpl);

    const { result } = renderHook(
      () => usePresentationTemplate(1),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(tmpl);
    expect(api.getPresentationTemplate).toHaveBeenCalledWith(1);
  });

  it("does not fetch when version is 0", () => {
    const { result } = renderHook(
      () => usePresentationTemplate(0),
      { wrapper: createWrapper() },
    );

    expect(result.current.isLoading).toBe(false);
    expect(api.getPresentationTemplate).not.toHaveBeenCalled();
  });
});
