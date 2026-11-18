/**
 * API client tests with a mocked global fetch.
 * Covers success, API errors, network failures, and request formatting.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, API_BASE_URL } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("exposes the local default base URL", () => {
    expect(API_BASE_URL).toBe("http://127.0.0.1:8000");
  });

  it("health returns parsed body", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(200, { status: "ok", version: "0.2.0", service: "agentfence-api" }),
    );
    const health = await api.health();
    expect(health.status).toBe("ok");
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/health`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("listScans builds query params", async () => {
    const fn = mockFetch(200, { scans: [], total: 0, limit: 10, offset: 5 });
    vi.stubGlobal("fetch", fn);
    await api.listScans({ limit: 10, offset: 5, order: "asc", severity: "high" });
    expect(fn).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/scans?limit=10&offset=5&order=asc&severity=high`,
      expect.anything(),
    );
  });

  it("runScan posts JSON body", async () => {
    const fn = mockFetch(200, { scan_id: "abc", risk_score: 0, result: {} });
    vi.stubGlobal("fetch", fn);
    const out = await api.runScan("./target");
    expect(out.scan_id).toBe("abc");
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/v1/scan`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ path: "./target" }));
  });

  it("throws ApiError with server detail on HTTP error", async () => {
    vi.stubGlobal("fetch", mockFetch(404, { detail: "scan not found: x" }));
    await expect(api.getScan("x")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "scan not found: x",
    });
  });

  it("throws ApiError with connection hint on network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(api.health()).rejects.toSatisfy((e: unknown) => {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).status).toBe(0);
      expect((e as ApiError).message).toContain("agentfence dashboard");
      return true;
    });
  });

  it("falls back to status text when error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not json", { status: 500 })),
    );
    const err = await api.summary().catch((e: unknown) => e as ApiError);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
  });
});
