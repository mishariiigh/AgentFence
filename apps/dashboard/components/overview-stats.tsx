"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { Card, StatCard } from "@/components/ui";
import { Loading, ErrorState, EmptyState } from "@/components/states";

export function OverviewStats() {
  const summary = useApiData(() => api.summary(), []);
  const scans = useApiData(() => api.listScans({ limit: 5 }), []);

  if (summary.state === "loading") return <Loading label="Loading overview…" />;
  if (summary.state === "error" || !summary.data)
    return <ErrorState message={summary.error ?? "Unknown error"} onRetry={summary.reload} />;

  const s = summary.data;
  const latest = scans.data?.scans.slice(0, 5) ?? [];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total scans" value={String(s.total_scans)} hint="stored locally in SQLite" />
        <StatCard label="Total findings" value={String(s.total_findings)} hint="across all scans" />
        <StatCard label="Critical findings" value={String(s.critical)} hint="needs immediate attention" />
        <StatCard label="High findings" value={String(s.high)} hint="fix soon" />
      </div>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Latest scan activity</h2>
          <Link href="/scans" className="text-xs text-primary hover:underline">
            View all scans →
          </Link>
        </div>
        {scans.state === "loading" ? (
          <Loading label="Loading recent scans…" />
        ) : scans.state === "error" ? (
          <ErrorState message={scans.error ?? "Unknown error"} onRetry={scans.reload} />
        ) : latest.length === 0 ? (
          <EmptyState
            title="No scans yet"
            hint="Run your first scan from the Scans page, or with `agentfence scan <path>` in the CLI."
          />
        ) : (
          <ul className="divide-y divide-border text-sm">
            {latest.map((scan) => (
              <li key={scan.scan_id} className="flex items-center justify-between py-2.5">
                <Link
                  href={`/scans/${scan.scan_id}`}
                  className="font-mono text-xs hover:text-primary"
                >
                  {scan.target_display}
                </Link>
                <span className="text-xs text-muted-foreground">
                  {scan.created_at} · {scan.total_findings} finding(s) · risk {scan.risk_score}/100
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Findings by severity</h2>
          <div className="space-y-2 text-sm">
            {(
              [
                ["critical", s.critical],
                ["high", s.high],
                ["medium", s.medium],
                ["low", s.low],
                ["info", s.info],
              ] as const
            ).map(([label, count]) => (
              <div key={label} className="flex items-center gap-3">
                <span className="w-16 capitalize text-muted-foreground">{label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{
                      width: `${s.total_findings ? Math.round((count / s.total_findings) * 100) : 0}%`,
                    }}
                  />
                </div>
                <span className="w-8 text-right tabular-nums">{count}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 text-sm font-semibold">About this data</h2>
          <p className="text-sm text-muted-foreground">
            All numbers come from real scans persisted in the local SQLite database
            (<code className="rounded bg-muted px-1">.agentfence/agentfence.db</code>). Secret
            values are redacted before storage. Attack Lab, Policies, Reports, and
            Settings remain demonstration/planned views until their backend
            integrations ship.
          </p>
        </Card>
      </div>
    </div>
  );
}
