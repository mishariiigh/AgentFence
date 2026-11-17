import { PageHeader, Card, Badge } from "@/components/ui";

// DEMONSTRATION RESULTS — mirror of the deterministic Attack Lab baseline
// suite shipped in benchmarks/scenarios. Run it live with `agentfence arena`.
const DEMO_RESULTS = [
  { name: "write-should-deny", expected: "deny", actual: "deny", passed: true },
  { name: "read-allowed-in-read-only-policy", expected: "allow", actual: "allow", passed: true },
  { name: "write-requires-approval", expected: "require_approval", actual: "require_approval", passed: true },
  { name: "read-denied-by-default", expected: "deny", actual: "deny", passed: true },
];

export default function ArenaPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Attack Lab"
        description="Safe, reproducible attack simulations. Scenarios are declarative YAML data — the engine never launches real agents, never executes payloads, and never touches external systems."
      />
      <Card>
        <div className="mb-4 flex items-center gap-2 text-sm">
          <Badge tone="success">Simulated & deterministic</Badge>
          <span className="text-muted-foreground">4/4 baseline scenarios passed (demo snapshot)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-3 pr-4 font-medium">Scenario</th>
                <th className="pb-3 pr-4 font-medium">Expected</th>
                <th className="pb-3 pr-4 font-medium">Actual</th>
                <th className="pb-3 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_RESULTS.map((r) => (
                <tr key={r.name} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-mono text-xs">{r.name}</td>
                  <td className="py-3 pr-4">{r.expected}</td>
                  <td className="py-3 pr-4">{r.actual}</td>
                  <td className="py-3">
                    <Badge tone={r.passed ? "success" : "critical"}>
                      {r.passed ? "PASS" : "FAIL"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="mt-4 text-xs text-muted-foreground">
        Run the real suite:{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">agentfence arena benchmarks/scenarios</code>
      </p>
    </div>
  );
}
