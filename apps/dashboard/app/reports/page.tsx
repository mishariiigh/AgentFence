"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

export default function ReportsPage() {
  const scans = useApiData(() => api.listScans({ limit: 10 }), []);
  const arena = useApiData(() => api.arenaRuns(10), []);
  const policyHistory = useApiData(() => api.policyHistory(10), []);

  return (
    <PageShell>
      <PageHeader
        title="Reports"
        description="Report information derived from persisted local data: security scans, Arena runs, and policy evaluations. No metrics are invented."
      />
      <ApiStatus />

      <div className="space-y-6">
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Security scan reports</h2>
            <Link href="/scans" className="text-xs text-primary hover:underline">
              Manage scans →
            </Link>
          </div>
          {scans.state === "loading" ? (
            <Loading />
          ) : scans.state === "error" ? (
            <ErrorState message={scans.error ?? "Unknown error"} onRetry={scans.reload} />
          ) : !scans.data || scans.data.scans.length === 0 ? (
            <EmptyState title="No scan reports" hint="Run a scan to generate report data." />
          ) : (
            <ul className="divide-y divide-border text-sm">
              {scans.data.scans.map((s) => (
                <li key={s.scan_id} className="flex items-center justify-between py-2.5">
                  <Link href={`/scans/${s.scan_id}`} className="font-mono text-xs hover:text-primary">
                    {s.target_display}
                  </Link>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    {s.created_at}
                    <Badge tone={s.risk_score >= 40 ? "high" : s.risk_score > 0 ? "medium" : "success"}>
                      risk {s.risk_score}/100 · {s.total_findings} finding(s)
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Arena run reports</h2>
            <Link href="/arena" className="text-xs text-primary hover:underline">
              Open Attack Lab →
            </Link>
          </div>
          {arena.state === "loading" ? (
            <Loading />
          ) : arena.state === "error" ? (
            <ErrorState message={arena.error ?? "Unknown error"} onRetry={arena.reload} />
          ) : !arena.data || arena.data.runs.length === 0 ? (
            <EmptyState title="No Arena reports" hint="Run the scenario suite to generate report data." />
          ) : (
            <ul className="divide-y divide-border text-sm">
              {arena.data.runs.map((r) => (
                <li key={r.run_id} className="flex items-center justify-between py-2.5">
                  <span className="font-mono text-xs">{r.run_id.slice(0, 8)}</span>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    {r.created_at}
                    <Badge tone={r.failed === 0 ? "success" : "critical"}>
                      {r.passed}/{r.scenario_count} passed · {Math.round(r.score * 100)}%
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Policy evaluation reports</h2>
            <Link href="/policies" className="text-xs text-primary hover:underline">
              Open Policies →
            </Link>
          </div>
          {policyHistory.state === "loading" ? (
            <Loading />
          ) : policyHistory.state === "error" ? (
            <ErrorState
              message={policyHistory.error ?? "Unknown error"}
              onRetry={policyHistory.reload}
            />
          ) : !policyHistory.data || policyHistory.data.evaluations.length === 0 ? (
            <EmptyState title="No policy evaluations" hint="Evaluate a policy action to create history." />
          ) : (
            <ul className="divide-y divide-border text-sm">
              {policyHistory.data.evaluations.map((e) => (
                <li key={e.evaluation_id} className="flex items-center justify-between py-2.5">
                  <span className="text-xs">
                    <span className="font-mono">{e.policy_name}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      · {e.action} on {e.resource}
                    </span>
                  </span>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    {e.created_at}
                    <Badge
                      tone={
                        e.decision === "allow"
                          ? "success"
                          : e.decision === "deny"
                            ? "critical"
                            : "warning"
                      }
                    >
                      {e.decision}
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="mb-2 text-sm font-semibold">Unavailable report types</h2>
          <p className="text-sm text-muted-foreground">
            Exportable artifact reports (SARIF, PDF, signed evidence bundles) are
            <Badge tone="neutral">planned</Badge> and listed in{" "}
            <code className="rounded bg-muted px-1">docs/ROADMAP.md</code>. CLI-generated
            JSON/Markdown scan reports remain available via{" "}
            <code className="rounded bg-muted px-1">agentfence scan &lt;path&gt; --report</code>.
          </p>
        </Card>
      </div>
    </PageShell>
  );
}
