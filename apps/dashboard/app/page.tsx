import { PageHeader, StatCard, Card, Badge } from "@/components/ui";

// DEMONSTRATION DATA — not live scan results. The dashboard will consume the
// local AgentFence API (POST /api/v1/scan) in a future milestone.
const DEMO_STATS = [
  { label: "Scans run (demo)", value: "3", hint: "via agentfence CLI" },
  { label: "Open findings (demo)", value: "5", hint: "1 high · 3 medium · 1 low" },
  { label: "Arena scenarios (demo)", value: "4/4", hint: "baseline suite passed" },
  { label: "Policies (demo)", value: "1", hint: "example-policy" },
];

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        description="Local-first security posture for your AI agents. All data shown here is demonstration data until you connect the local AgentFence API and run real scans."
      />
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">
        <Badge tone="warning">Demo data</Badge>
        Statistics below are illustrative placeholders, not measured results.
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {DEMO_STATS.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} hint={s.hint} />
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Getting started</h2>
          <ol className="list-inside list-decimal space-y-2 text-sm text-muted-foreground">
            <li>
              Run <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">agentfence init</code> in your project.
            </li>
            <li>
              Scan configurations:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">agentfence scan .</code>
            </li>
            <li>
              Validate policies:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">agentfence policy validate policies/example.yaml</code>
            </li>
            <li>
              Start this dashboard&apos;s API:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">agentfence dashboard</code>
            </li>
          </ol>
        </Card>
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Security posture by surface</h2>
          <div className="space-y-3 text-sm">
            {[
              { name: "Claude Code configs", tone: "medium" as const, label: "1 medium (demo)" },
              { name: "MCP servers", tone: "high" as const, label: "1 high (demo)" },
              { name: "Policies", tone: "success" as const, label: "valid" },
              { name: "Attack Lab", tone: "success" as const, label: "4/4 passed" },
            ].map((row) => (
              <div key={row.name} className="flex items-center justify-between">
                <span className="text-muted-foreground">{row.name}</span>
                <Badge tone={row.tone}>{row.label}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
