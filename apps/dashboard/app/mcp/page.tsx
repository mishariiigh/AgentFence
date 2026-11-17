import { PageHeader, Card, Badge } from "@/components/ui";

// DEMONSTRATION INSPECTION — read-only MCP config findings format, not a live
// inspection. Run the real thing with `agentfence mcp scan <path>`.
const DEMO_SERVERS = [
  { name: "filesystem", transport: "stdio", command: "npx -y @modelcontextprotocol/server-filesystem", issues: 0 },
  { name: "web-fetch", transport: "sse", url: "https://tools.example.com/sse", issues: 1 },
  { name: "legacy-db", transport: "stdio", command: "node db-server.js --no-verify", issues: 2 },
];

export default function McpPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="MCP Inspection"
        description="Read-only inspection of MCP server configurations. AgentFence never launches MCP servers and never executes their tools."
      />
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-3 pr-4 font-medium">Server</th>
                <th className="pb-3 pr-4 font-medium">Transport</th>
                <th className="pb-3 pr-4 font-medium">Endpoint / Command</th>
                <th className="pb-3 font-medium">Issues</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_SERVERS.map((s) => (
                <tr key={s.name} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-medium">{s.name}</td>
                  <td className="py-3 pr-4">
                    <Badge tone="info">{s.transport}</Badge>
                  </td>
                  <td className="py-3 pr-4 font-mono text-xs">{s.command ?? s.url}</td>
                  <td className="py-3">
                    <Badge tone={s.issues === 0 ? "success" : s.issues === 1 ? "medium" : "high"}>
                      {s.issues === 0 ? "clean" : `${s.issues} finding(s)`}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="mt-4">
        <h2 className="mb-2 text-sm font-semibold">What the inspector checks</h2>
        <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
          <li>Hardcoded secrets in server <code className="rounded bg-muted px-1">env</code> blocks (redacted in output)</li>
          <li>TLS verification bypass flags such as <code className="rounded bg-muted px-1">--no-verify</code></li>
          <li>Non-HTTPS remote endpoints</li>
          <li>Suspicious commands (network/eval tokens)</li>
        </ul>
      </Card>
    </div>
  );
}
