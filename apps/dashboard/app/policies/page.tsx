import { PageHeader, Card, Badge } from "@/components/ui";

const DEMO_RULES = [
  { id: "allow-read-docs", action: "read", resource: "docs/*", decision: "allow" },
  { id: "approval-writes", action: "write", resource: "docs/*", decision: "require_approval" },
  { id: "deny-secrets", action: "read", resource: "secrets/*", decision: "deny" },
];

const TONES: Record<string, "success" | "warning" | "critical"> = {
  allow: "success",
  require_approval: "warning",
  deny: "critical",
};

export default function PoliciesPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Policy Management"
        description="Deterministic allow / deny / require-approval policies. Decisions are computed exclusively by explicit validated rules — never by an LLM."
      />
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Badge tone="success">example-policy · valid</Badge>
          <span className="text-xs text-muted-foreground">
            default: deny · 3 rules (demo snapshot of policies/example.yaml)
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-3 pr-4 font-medium">Rule ID</th>
                <th className="pb-3 pr-4 font-medium">Action</th>
                <th className="pb-3 pr-4 font-medium">Resource</th>
                <th className="pb-3 font-medium">Decision</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_RULES.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-mono text-xs">{r.id}</td>
                  <td className="py-3 pr-4 font-mono text-xs">{r.action}</td>
                  <td className="py-3 pr-4 font-mono text-xs">{r.resource}</td>
                  <td className="py-3">
                    <Badge tone={TONES[r.decision]}>{r.decision}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="mt-4 text-xs text-muted-foreground">
        Validate policies with{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">agentfence policy validate &lt;path&gt;</code> and evaluate
        decisions with <code className="rounded bg-muted px-1.5 py-0.5">agentfence policy evaluate &lt;path&gt; &lt;action&gt; &lt;resource&gt;</code>.
      </p>
    </div>
  );
}
