import { PageHeader, Card } from "@/components/ui";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Settings"
        description="AgentFence operates locally-first. These are the current security-relevant defaults of the platform."
      />
      <div className="space-y-4">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Security defaults</h2>
          <dl className="space-y-2 text-sm">
            {[
              ["Telemetry", "Disabled. AgentFence never sends data anywhere."],
              ["Scanned source code", "Never uploaded — all processing is local."],
              ["Scanned files", "Never executed. Inspection is static and read-only."],
              ["Agents / MCP servers", "Never launched during scanning."],
              ["Secrets", "Redacted in logs, findings evidence, and reports."],
              ["Policy decisions", "Deterministic rule evaluation only; no LLM involvement."],
            ].map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-4">
                <dt className="w-44 shrink-0 font-medium">{k}</dt>
                <dd className="text-muted-foreground">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Local API</h2>
          <p className="text-sm text-muted-foreground">
            The dashboard consumes the local API started with{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">agentfence dashboard</code> (default{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">http://127.0.0.1:8000</code>). Configure the base URL via{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">NEXT_PUBLIC_AGENTFENCE_API</code> once API integration lands
            in the dashboard.
          </p>
        </Card>
      </div>
    </div>
  );
}
