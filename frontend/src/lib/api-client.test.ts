import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

function clearStorage() {
  try {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  } catch {
    // no-op if localStorage unavailable
  }
}

describe("api-client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
    clearStorage();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearStorage();
    vi.resetModules();
  });

  describe("ApiError", () => {
    it("is thrown on non-ok response", async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(JSON.stringify({ detail: "not found" }), { status: 404 })
      );

      const mod = await import("@/lib/api-client");
      await expect(mod.api.listProjects()).rejects.toThrow("not found");
    });
  });

  describe("request()", () => {
    it("includes auth header when token exists", async () => {
      try {
        localStorage.setItem("access_token", "my-token");
      } catch {
        return; // skip if localStorage unavailable
      }
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(JSON.stringify([]), { status: 200 })
      );

      const mod = await import("@/lib/api-client");
      await mod.api.listProjects();

      const [, options] = vi.mocked(globalThis.fetch).mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers?.Authorization).toBe("Bearer my-token");
    });

    it("throws on forbidden response", async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(JSON.stringify({ detail: "forbidden" }), { status: 403 })
      );

      const mod = await import("@/lib/api-client");
      await expect(mod.api.listProjects()).rejects.toThrow("forbidden");
    });

    it("works without auth token", async () => {
      vi.mocked(globalThis.fetch).mockResolvedValue(
        new Response(JSON.stringify([]), { status: 200 })
      );

      const mod = await import("@/lib/api-client");
      const result = await mod.api.listProjects();
      expect(result).toEqual([]);
    });
  });
});
