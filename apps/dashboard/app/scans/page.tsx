import { PageHeader, Card, Badge } from "@/components/ui";

const DEMO_SCANS = [
  {
    target: "./claude-project/settings.json",
    when: "2026-11-17 14:02",
    files: 3,
    findings: 2,
    score: 24,
    label: "moderate",
    tone: "medium" as const,
  },
  {
    target: "./team-tools/.mcp.json",
    when: "2026-11-17 13:40",
    files: 1,
    findings: 3,
    score: 45,
    label: "high",
    tone: "high" as const,
  },
  {
    target: "./example-agent (clean)",
    when: "2026-11-17 13:12",
    files: 2,
    findings: 0,
    score: 0,
    label: "clean",
    tone: "success" as const,
  },
];

export default function ScansPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Security Scans"
        description="Read-only static scans of AI agent configuration files. Scanned files are never executed and no agents are launched. Rows below are demonstration data."
      />
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-3 pr-4 font-medium">Target</th>
                <th className="pb-3 pr-4 font-medium">When</th>
                <th className="pb-3 pr-4 font-medium">Files</th>
                <th className="pb-3 pr-4 font-medium">Findings</th>
                <th className="pb-3 font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_SCANS.map((s) => (
                <tr key={s.target} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-mono text-xs">{s.target}</td>
                  <td className="py-3 pr-4 text-muted-foreground">{s.when}</td>
                  <td className="py-3 pr-4">{s.files}</td>
                  <td className="py-3 pr-4">{s.findings}</td>
                  <td className="py-3">
                    <Badge tone={s.tone}>
                      {s.score}/100 · {s.label}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="mt-4 text-xs text-muted-foreground">
        Run real scans with <code className="rounded bg-muted px-1.5 py-0.5">agentfence scan &lt;path&gt; --json</code> or
        via the local API endpoint <code className="rounded bg-muted px-1.5 py-0.5">POST /api/v1/scan</code>.
      </p>
    </div>
  );
}
