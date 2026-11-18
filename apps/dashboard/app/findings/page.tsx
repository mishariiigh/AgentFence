"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Severity } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

const SEVERITIES: (Severity | "all")[] = ["all", "critical", "high", "medium", "low", "info"];

const TONES: Record<string, "critical" | "high" | "medium" | "low" | "info"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
  info: "info",
};

export default function FindingsPage() {
  const [severity, setSeverity] = useState<Severity | "all">("all");

  // Findings are fetched per-scan via the scan detail endpoint.
  const details = useApiData(async () => {
    const list = await api.listScans({ limit: 50 });
    const results = await Promise.all(
      list.scans.map(async (s) => {
        const d = await api.getScan(s.scan_id);
        return d.findings.map((f) => ({
          rule_id: f.rule_id,
          title: f.title,
          severity: f.severity,
          file_ref: f.file_ref,
          remediation: f.remediation,
          scan_id: s.scan_id,
        }));
      }),
    );
    return results.flat();
  }, []);

  const filtered =
    details.data?.filter((f) => severity === "all" || f.severity === severity) ?? [];

  return (
    <PageShell>
      <PageHeader
        title="Findings"
        description="Findings aggregated from all persisted scans. Secret values are redacted before storage."
      />
      <ApiStatus />

      <div className="mb-4 flex flex-wrap gap-2">
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverity(s)}
            className={`rounded-lg border px-3 py-1.5 text-xs capitalize ${
              severity === s
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {details.state === "loading" ? (
        <Loading label="Loading findings…" />
      ) : details.state === "error" ? (
        <ErrorState message={details.error ?? "Unknown error"} onRetry={details.reload} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={severity === "all" ? "No findings recorded" : `No ${severity} findings`}
          hint="Run a scan from the Scans page to collect findings."
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((f, i) => (
            <Card key={`${f.scan_id}-${f.rule_id}-${i}`} className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={TONES[f.severity] ?? "info"}>{f.severity.toUpperCase()}</Badge>
                <span className="font-medium">{f.title}</span>
                <Link
                  href={`/scans/${f.scan_id}`}
                  className="ml-auto text-xs text-primary hover:underline"
                >
                  View scan →
                </Link>
              </div>
              <div className="font-mono text-xs text-muted-foreground">
                {f.rule_id}
                {f.file_ref ? ` · ${f.file_ref}` : ""}
              </div>
              <p className="text-sm text-muted-foreground">
                <span className="text-foreground">Remediation:</span> {f.remediation}
              </p>
            </Card>
          ))}
        </div>
      )}
    </PageShell>
  );
}
