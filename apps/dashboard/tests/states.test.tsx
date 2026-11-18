/**
 * Component tests for state components: loading, empty, and error handling.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorState, EmptyState, Loading } from "@/components/states";

describe("Loading", () => {
  it("shows its label", () => {
    render(<Loading label="Loading scans…" />);
    expect(screen.getByText("Loading scans…")).toBeTruthy();
  });
});

describe("EmptyState", () => {
  it("shows title and hint", () => {
    render(<EmptyState title="No scans" hint="Run one first" />);
    expect(screen.getByText("No scans")).toBeTruthy();
    expect(screen.getByText("Run one first")).toBeTruthy();
  });
});

describe("ErrorState", () => {
  it("shows the error message", () => {
    render(<ErrorState message="Cannot reach the API" />);
    expect(screen.getByText("Cannot reach the API")).toBeTruthy();
  });

  it("calls onRetry when Retry is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="boom" onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders without a retry button", () => {
    render(<ErrorState message="boom" />);
    expect(screen.queryByText("Retry")).toBeNull();
  });
});
