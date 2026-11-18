"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError, type ScanSummaryDto } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

function riskTone(score: number): "critical" | "high" | "medium" | "success" | "low" {
  if (score >= 70) return "critical";
  if (score >= 40) return "high";
  if (score >= 15) return "medium";
  if (score > 0) return "low";
  return "success";
}

function ScanRow({ scan }: { scan: ScanSummaryDto }) {
  return (
    <tr className="border-b last:border-0 hover:bg-accent/40">
      <td className="py-3 pr-4">
        <Link href={`/scans/${scan.scan_id}`} className="font-mono text-xs hover:text-primary">
          {scan.target_display}
        </Link>
      </td>
      <td className="py-3 pr-4 text-xs text-muted-foreground">{scan.created_at}</td>
      <td className="py-3 pr-4">
        <Badge tone={scan.kind === "scan" ? "info" : "neutral"}>{scan.kind}</Badge>
      </td>
      <td className="py-3 pr-4">{scan.total_findings}</td>
      <td className="py-3">
        <Badge tone={riskTone(scan.risk_score)}>
          {scan.risk_score}/100
        </Badge>
      </td>
    </tr>
  );
}

export default function ScansPage() {
  const [pathInput, setPathInput] = useState("");
  const [running, setRunning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [lastScanId, setLastScanId] = useState<string | null>(null);
  const history = useApiData(() => api.listScans({ limit: 50 }), []);

  async function runScan(e: React.FormEvent) {
    e.preventDefault();
    if (!pathInput.trim() || running) return;
    setRunning(true);
    setScanError(null);
    setLastScanId(null);
    try {
      const started = await api.runScan(pathInput.trim());
      setLastScanId(started.scan_id);
      setPathInput("");
      history.reload();
    } catch (err) {
      setScanError(
        err instanceof ApiError ? err.message : "Scan failed unexpectedly",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Security Scans"
        description="Read-only scans of AI agent configuration files, persisted in local SQLite history. Scanned files are never executed."
      />
      <ApiStatus />

      <Card className="mb-6">
        <form onSubmit={runScan} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="Absolute or relative path to scan (e.g. ~/my-project)"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={running || !pathInput.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {running ? "Scanning…" : "Run scan"}
          </button>
        </form>
        {scanError ? (
          <p className="mt-3 text-sm text-red-300">{scanError}</p>
        ) : lastScanId ? (
          <p className="mt-3 text-sm text-emerald-300">
            Scan complete.{" "}
            <Link href={`/scans/${lastScanId}`} className="underline">
              View results →
            </Link>
          </p>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            Local filesystem paths only — remote URLs are rejected by the API.
          </p>
        )}
      </Card>

      {history.state === "loading" ? (
        <Loading label="Loading scan history…" />
      ) : history.state === "error" ? (
        <ErrorState message={history.error ?? "Unknown error"} onRetry={history.reload} />
      ) : history.data && history.data.scans.length === 0 ? (
        <EmptyState
          title="No scans in history"
          hint="Run your first scan above or with `agentfence scan <path>`."
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">Target</th>
                  <th className="pb-3 pr-4 font-medium">Date (UTC)</th>
                  <th className="pb-3 pr-4 font-medium">Kind</th>
                  <th className="pb-3 pr-4 font-medium">Findings</th>
                  <th className="pb-3 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {history.data?.scans.map((scan) => <ScanRow key={scan.scan_id} scan={scan} />)}
              </tbody>
            </table>
          </div>
          {history.data && history.data.total > history.data.scans.length ? (
            <p className="mt-3 text-xs text-muted-foreground">
              Showing {history.data.scans.length} of {history.data.total} scans.
            </p>
          ) : null}
        </Card>
      )}
    </PageShell>
  );
}
