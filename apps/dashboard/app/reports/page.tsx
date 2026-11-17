import { PageHeader, Card, Badge } from "@/components/ui";

// DEMONSTRATION REPORTS — report artifacts produced by
// `agentfence scan <path> --report <file>`; listing below is illustrative.
const DEMO_REPORTS = [
  { name: "agentfence-report-settings.json", format: "JSON", risk: 24, when: "2026-11-17 14:05" },
  { name: "agentfence-report-mcp.md", format: "Markdown", risk: 45, when: "2026-11-17 13:45" },
  { name: "agentfence-report-clean.json", format: "JSON", risk: 0, when: "2026-11-17 13:15" },
];

export default function ReportsPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Reports"
        description="Structured security reports and evidence. Reports redact secret values automatically and record that inspection was read-only."
      />
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-3 pr-4 font-medium">Report</th>
                <th className="pb-3 pr-4 font-medium">Format</th>
                <th className="pb-3 pr-4 font-medium">Risk score</th>
                <th className="pb-3 font-medium">Generated</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_REPORTS.map((r) => (
                <tr key={r.name} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-mono text-xs">{r.name}</td>
                  <td className="py-3 pr-4">{r.format}</td>
                  <td className="py-3 pr-4">
                    <Badge tone={r.risk === 0 ? "success" : r.risk >= 40 ? "high" : "medium"}>
                      {r.risk}/100
                    </Badge>
                  </td>
                  <td className="py-3 text-muted-foreground">{r.when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="mt-4 text-xs text-muted-foreground">
        Generate reports:{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">agentfence scan &lt;path&gt; --report report.json</code>
      </p>
    </div>
  );
}
