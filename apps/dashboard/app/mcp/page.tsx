"use client";

import { useState } from "react";
import { api, ApiError, type ScanStartedDto } from "@/lib/api";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { PageShell } from "@/components/states";

const TONES: Record<string, "critical" | "high" | "medium" | "low" | "info"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
  info: "info",
};

export default function McpPage() {
  const [pathInput, setInput] = useState(".mcp.json");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ScanStartedDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function inspect(e: React.FormEvent) {
    e.preventDefault();
    if (!pathInput.trim() || running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.inspectMcp(pathInput.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Inspection failed unexpectedly");
    } finally {
      setRunning(false);
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="MCP Inspection"
        description="Read-only inspection of MCP server configurations via the live API. AgentFence never launches MCP servers or executes their tools."
      />
      <ApiStatus />

      <Card className="mb-6">
        <form onSubmit={inspect} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={pathInput}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Path to MCP config file (e.g. .mcp.json)"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={running || !pathInput.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {running ? "Inspecting…" : "Inspect config"}
          </button>
        </form>
        {error ? <p className="mt-3 text-sm text-red-300">{error}</p> : null}
      </Card>

      {result ? (
        <Card>
          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
            <Badge tone={result.risk_score > 0 ? "medium" : "success"}>
              Risk {result.risk_score}/100
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {result.result.target} · {result.result.files_inspected} file(s) inspected
            </span>
          </div>
          {result.result.findings.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No findings — the MCP configuration looks clean.
            </p>
          ) : (
            <div className="space-y-3">
              {result.result.findings.map((f) => (
                <div key={f.id} className="rounded-lg border border-border p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge tone={TONES[f.severity] ?? "info"}>
                      {f.severity.toUpperCase()}
                    </Badge>
                    <span className="font-medium">{f.title}</span>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{f.description}</p>
                  <p className="mt-1 text-sm">
                    <span className="font-medium">Remediation:</span>{" "}
                    <span className="text-muted-foreground">{f.remediation}</span>
                  </p>
                  {f.evidence ? (
                    <p className="mt-1 font-mono text-xs text-muted-foreground">
                      Evidence: <code className="rounded bg-muted px-1">{f.evidence}</code>
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            This inspection has been persisted to scan history (kind: mcp_inspection).
          </p>
        </Card>
      ) : (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">What the inspector checks</h2>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            <li>Hardcoded secrets in server <code className="rounded bg-muted px-1">env</code> blocks (redacted in output)</li>
            <li>TLS verification bypass flags such as <code className="rounded bg-muted px-1">--no-verify</code></li>
            <li>Non-HTTPS remote endpoints</li>
            <li>Suspicious commands (network/eval tokens)</li>
          </ul>
        </Card>
      )}
    </PageShell>
  );
}
