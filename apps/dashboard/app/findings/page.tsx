import { PageHeader, Card, Badge } from "@/components/ui";

type Finding = {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  file: string;
  remediation: string;
};

// DEMONSTRATION FINDINGS — examples of the structured finding format, not
// results from a real scan.
const DEMO_FINDINGS: Finding[] = [
  {
    id: "AF-AUTO_APPROVE_ALL",
    title: "All tool calls auto-approved",
    severity: "critical",
    file: "settings.json",
    remediation: "Disable auto_approve_all; use explicit allow-lists with approval gates.",
  },
  {
    id: "AF-MCP-ENV-SECRET",
    title: "Possible hardcoded secret in MCP server env",
    severity: "high",
    file: ".mcp.json",
    remediation: "Reference the value from the environment; rotate if committed.",
  },
  {
    id: "AF-MCP-INSECURE-URL",
    title: "Insecure URL for MCP server",
    severity: "medium",
    file: "mcp.json",
    remediation: "Use https:// endpoints for remote MCP servers.",
  },
  {
    id: "AF-SUSPICIOUS-INSTRUCTION",
    title: "Suspicious instruction pattern in configuration",
    severity: "medium",
    file: "instructions.yaml",
    remediation: "Remove instructions that override safety behavior.",
  },
  {
    id: "AF-PARSE-ERROR",
    title: "Configuration file failed to parse",
    severity: "low",
    file: "agent.yaml",
    remediation: "Fix the syntax so automated inspection can evaluate the file.",
  },
];

const TONES: Record<Finding["severity"], "critical" | "high" | "medium" | "low" | "info"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
  info: "info",
};

export default function FindingsPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Findings"
        description="Structured findings with severity, explanation, and remediation guidance. Secret values are always redacted in evidence. List below is demonstration data."
      />
      <div className="space-y-3">
        {DEMO_FINDINGS.map((f) => (
          <Card key={f.id} className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <Badge tone={TONES[f.severity]}>{f.severity.toUpperCase()}</Badge>
                <span className="font-medium">{f.title}</span>
              </div>
              <div className="font-mono text-xs text-muted-foreground">
                {f.id} · {f.file}
              </div>
              <p className="max-w-2xl text-sm text-muted-foreground">
                <span className="text-foreground">Remediation:</span> {f.remediation}
              </p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
