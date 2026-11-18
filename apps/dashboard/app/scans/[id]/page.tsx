"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { api, type FindingDto } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

const SEVERITY_TONES: Record<string, "critical" | "high" | "medium" | "low" | "info"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
  info: "info",
};

function FindingCard({ finding }: { finding: FindingDto }) {
  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={SEVERITY_TONES[finding.severity] ?? "info"}>
          {finding.severity.toUpperCase()}
        </Badge>
        <span className="font-medium">{finding.title}</span>
      </div>
      <div className="font-mono text-xs text-muted-foreground">
        {finding.rule_id}
        {finding.file_ref ? ` · ${finding.file_ref}` : ""}
      </div>
      <p className="text-sm text-muted-foreground">{finding.description}</p>
      <p className="text-sm">
        <span className="font-medium">Remediation:</span>{" "}
        <span className="text-muted-foreground">{finding.remediation}</span>
      </p>
      {finding.evidence ? (
        <p className="font-mono text-xs text-muted-foreground">
          Evidence: <code className="rounded bg-muted px-1">{finding.evidence}</code>
        </p>
      ) : null}
    </Card>
  );
}

export default function ScanDetailPage() {
  const params = useParams<{ id: string }>();
  const scanId = params?.id;
  const detail = useApiData(() => api.getScan(scanId as string), [scanId]);

  return (
    <PageShell>
      <PageHeader
        title="Scan Details"
        description="Actual findings from a persisted scan, as stored in the local SQLite database."
      />
      <ApiStatus />
      {!scanId ? (
        <EmptyState title="No scan selected" hint="Pick a scan from the Scans page." />
      ) : detail.state === "loading" ? (
        <Loading label="Loading scan…" />
      ) : detail.state === "error" ? (
        <ErrorState message={detail.error ?? "Unknown error"} onRetry={detail.reload} />
      ) : detail.data ? (
        <div className="space-y-6">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-mono text-sm">{detail.data.scan.target_display}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {detail.data.scan.created_at} · {detail.data.scan.kind} ·{" "}
                  {detail.data.scan.files_inspected} file(s) inspected · scanner v
                  {detail.data.scan.scanner_version}
                </div>
              </div>
              <Badge tone={detail.data.scan.risk_score >= 40 ? "high" : "medium"}>
                Risk {detail.data.scan.risk_score}/100
              </Badge>
            </div>
          </Card>

          {detail.data.findings.length === 0 ? (
            <EmptyState
              title="No findings in this scan"
              hint="The scanned configuration produced no security findings."
            />
          ) : (
            <div className="space-y-3">
              {detail.data.findings.map((f) => (
                <FindingCard key={f.finding_pk} finding={f} />
              ))}
            </div>
          )}

          <Link href="/scans" className="inline-block text-sm text-primary hover:underline">
            ← Back to all scans
          </Link>
        </div>
      ) : null}
    </PageShell>
  );
}
