/**
 * Component tests for security-related dashboard components:
 * the API connection status indicator (loading/online/offline).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ApiStatus } from "@/components/api-status";
import { RunResults } from "@/components/arena-results";

const healthSuccess = vi.fn().mockResolvedValue({ status: "ok" });
const healthFail = vi.fn().mockRejectedValue(new Error("down"));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, health: (...args: unknown[]) => healthMock(...args) },
  };
});

const healthMock = vi.fn();

beforeEach(() => {
  healthMock.mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => vi.useRealTimers());

describe("ApiStatus", () => {
  it("shows offline state and recovery when API fails then succeeds", async () => {
    healthMock.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ status: "ok" });
    render(<ApiStatus />);
    await waitFor(() => expect(screen.getByText(/API offline/)).toBeTruthy());
    // interval retry succeeds → shows online
    await vi.advanceTimersByTimeAsync(15000);
    await waitFor(() => expect(screen.getByText("API connected")).toBeTruthy());
  });

  it("shows connected state on success", async () => {
    healthMock.mockResolvedValue({ status: "ok" });
    render(<ApiStatus />);
    await waitFor(() => expect(screen.getByText("API connected")).toBeTruthy());
  });
});

describe("RunResults (Arena)", () => {
  const run = {
    run_id: "abc123",
    passed: 2,
    failed: 1,
    score: 2 / 3,
    results: [
      {
        scenario: "write-should-deny",
        expected: "deny",
        actual: "deny",
        passed: true,
        explanation: "Denied by default",
        matched_rule: null,
      },
      {
        scenario: "read-allowed",
        expected: "allow",
        actual: "allow",
        passed: true,
        explanation: "Allowed by rule",
        matched_rule: "r1",
      },
      {
        scenario: "broken-scenario",
        expected: "allow",
        actual: "deny",
        passed: false,
        explanation: "No rule matched; default deny applied",
        matched_rule: null,
      },
    ],
  };

  it("renders pass/fail summary with score", () => {
    render(<RunResults run={run} />);
    expect(screen.getByText("2/3 passed")).toBeTruthy();
    expect(screen.getByText(/Score: 67%/)).toBeTruthy();
  });

  it("renders PASS and FAIL per scenario with explanations", () => {
    render(<RunResults run={run} />);
    expect(screen.getAllByText("PASS").length).toBe(2);
    expect(screen.getAllByText("FAIL").length).toBe(1);
    expect(screen.getByText(/Denied by default/)).toBeTruthy();
    expect(screen.getByText(/default deny applied/)).toBeTruthy();
    expect(screen.getByText(/expected: deny · actual: deny/)).toBeTruthy();
  });
});

void healthSuccess;
void healthFail;
