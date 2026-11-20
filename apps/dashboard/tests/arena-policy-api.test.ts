/**
 * Tests for Arena/Policies API client methods and the session-token header
 * behavior required by the local-security model.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

function mockFetch(status: number, body: unknown, count = 1) {
  const fn = vi.fn();
  for (let i = 0; i < count; i++) {
    fn.mockResolvedValueOnce(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => vi.unstubAllGlobals());

describe("arena & policy api client", () => {
  it("arenaRun posts scenario_ids (null for all)", async () => {
    const fn = mockFetch(200, { run_id: "r1", passed: 4, results: [] }, 2);
    await api.arenaRun();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ scenario_ids: null }));
    await api.arenaRun(["a", "b"]);
    const [, init2] = (fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(init2.body).toBe(JSON.stringify({ scenario_ids: ["a", "b"] }));
    void fn;
  });

  it("policyValidate posts content and returns problems", async () => {
    mockFetch(200, { valid: false, problems: ["bad"] });
    const out = await api.policyValidate("name: [x");
    expect(out.valid).toBe(false);
    expect(out.problems).toEqual(["bad"]);
  });

  it("policyEvaluate posts action/resource and parses decision", async () => {
    mockFetch(200, {
      policy: "p",
      action: "read",
      resource: "docs/*",
      decision: "allow",
      matched_rule: "r1",
      explanation: "Allowed by rule r1",
    });
    const out = await api.policyEvaluate({ content: "name: p", action: "read", resource: "docs/*" });
    expect(out.decision).toBe("allow");
    expect(out.matched_rule).toBe("r1");
  });

  it("policyEvaluate 422 surfaces server detail", async () => {
    mockFetch(422, { detail: "policy is invalid" });
    const err = await api
      .policyEvaluate({ content: "bad", action: "read", resource: "x" })
      .catch((e: unknown) => e as ApiError);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).message).toContain("invalid");
  });

  it("arenaRuns and policyHistory build paginated URLs", async () => {
    const fn = mockFetch(200, { runs: [], total: 0, limit: 5, offset: 10 });
    fn.mockResolvedValueOnce(
      new Response(JSON.stringify({ evaluations: [], limit: 5, offset: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await api.arenaRuns(5, 10);
    expect(fn.mock.calls[0][0]).toContain("/api/v1/arena/runs?limit=5&offset=10");
    await api.policyHistory(5, 0);
    expect(fn.mock.calls[1][0]).toContain("/api/v1/policies/history?limit=5&offset=0");
  });

  it("sets session token header on mutating requests when configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENTFENCE_TOKEN", "secret-token");
    vi.resetModules();
    const { api: freshApi } = await import("@/lib/api");
    const fn = mockFetch(200, { run_id: "r", passed: 0, results: [] });
    await freshApi.arenaRun();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.get("X-AgentFence-Session")).toBe("secret-token");
    void fn;
    vi.unstubAllEnvs();
  });

  it("does not set session token on GET requests", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENTFENCE_TOKEN", "secret-token");
    vi.resetModules();
    const { api: freshApi } = await import("@/lib/api");
    mockFetch(200, []);
    await freshApi.arenaScenarios();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.get("X-AgentFence-Session")).toBeNull();
    vi.unstubAllEnvs();
  });
});
