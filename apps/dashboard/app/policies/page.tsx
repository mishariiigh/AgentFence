"use client";

import { useState } from "react";
import { api, ApiError, type PolicyEvaluationDto } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

const DECISION_TONES: Record<string, "success" | "warning" | "critical" | "neutral"> = {
  allow: "success",
  require_approval: "warning",
  deny: "critical",
  invalid_policy: "neutral",
};

const SAMPLE_POLICY = `name: my-policy
default: deny
rules:
  - id: allow-read-docs
    action: read
    resource: "docs/*"
    decision: allow
  - id: approval-writes
    action: write
    resource: "*"
    decision: require_approval
`;

export default function PoliciesPage() {
  const policies = useApiData(() => api.policies(), []);
  const history = useApiData(() => api.policyHistory(10), []);

  const [policyText, setPolicyText] = useState(SAMPLE_POLICY);
  const [validation, setValidation] = useState<{ valid: boolean; problems: string[] } | null>(null);
  const [action, setAction] = useState("read");
  const [resource, setResource] = useState("docs/report.md");
  const [decision, setDecision] = useState<PolicyEvaluationDto | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [working, setWorking] = useState<"validate" | "evaluate" | null>(null);

  async function validate() {
    setWorking("validate");
    setValidation(null);
    try {
      setValidation(await api.policyValidate(policyText));
    } catch (err) {
      setValidation({ valid: false, problems: [err instanceof ApiError ? err.message : "Validation failed"] });
    } finally {
      setWorking(null);
    }
  }

  async function evaluate() {
    setWorking("evaluate");
    setEvalError(null);
    setDecision(null);
    try {
      setDecision(await api.policyEvaluate({ content: policyText, action, resource }));
      history.reload();
    } catch (err) {
      setEvalError(err instanceof ApiError ? err.message : "Evaluation failed");
    } finally {
      setWorking(null);
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Policy Management"
        description="Deterministic allow / deny / require-approval policies, validated and evaluated by explicit rules — never by an LLM."
      />
      <ApiStatus />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Validate &amp; evaluate a policy</h2>
          <textarea
            value={policyText}
            onChange={(e) => setPolicyText(e.target.value)}
            rows={12}
            spellCheck={false}
            className="w-full rounded-lg border border-border bg-background p-3 font-mono text-xs outline-none focus:border-primary"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={validate}
              disabled={working !== null}
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            >
              {working === "validate" ? "Validating…" : "Validate"}
            </button>
          </div>
          {validation ? (
            <div className="mt-3 rounded-lg border border-border p-3 text-sm">
              <Badge tone={validation.valid ? "success" : "critical"}>
                {validation.valid ? "Valid policy" : "Invalid policy"}
              </Badge>
              {validation.problems.length > 0 ? (
                <ul className="mt-2 list-inside list-disc text-xs text-red-300">
                  {validation.problems.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <input
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="action (e.g. read)"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            />
            <input
              value={resource}
              onChange={(e) => setResource(e.target.value)}
              placeholder="resource (e.g. docs/*)"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
          <button
            onClick={evaluate}
            disabled={working !== null}
            className="mt-3 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {working === "evaluate" ? "Evaluating…" : "Evaluate action"}
          </button>
          {evalError ? (
            <div className="mt-3">
              <ErrorState message={evalError} onRetry={evaluate} />
            </div>
          ) : null}
          {decision ? (
            <div className="mt-3 rounded-lg border border-border p-3 text-sm">
              <div className="flex items-center gap-2">
                <Badge tone={DECISION_TONES[decision.decision] ?? "neutral"}>
                  {decision.decision.toUpperCase()}
                </Badge>
                <span className="text-muted-foreground">
                  {decision.action} on {decision.resource}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{decision.explanation}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Matched rule: {decision.matched_rule ?? "none (default applied)"}
              </p>
            </div>
          ) : null}
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Policy catalogue</h2>
            {policies.state === "loading" ? (
              <Loading label="Loading policies…" />
            ) : policies.state === "error" ? (
              <ErrorState message={policies.error ?? "Unknown error"} onRetry={policies.reload} />
            ) : !policies.data || policies.data.policies.length === 0 ? (
              <EmptyState
                title="No policy files found"
                hint="Add YAML policies to policies/ or .agentfence/policies/."
              />
            ) : (
              <div className="space-y-3">
                {policies.data.policies.map((p) => (
                  <div key={`${p.directory}/${p.file}`} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-medium">{p.name}</span>
                      <Badge tone={p.valid ? "success" : "critical"}>
                        {p.valid ? "valid" : "invalid"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {p.file} · {p.rule_count} rule(s) · default: {p.default ?? "n/a"}
                      </span>
                    </div>
                    {p.rules.length > 0 ? (
                      <table className="mt-2 w-full text-xs">
                        <tbody>
                          {p.rules.map((r) => (
                            <tr key={r.id} className="border-t border-border">
                              <td className="py-1 pr-2 font-mono">{r.id}</td>
                              <td className="py-1 pr-2 font-mono text-muted-foreground">{r.action}</td>
                              <td className="py-1 pr-2 font-mono text-muted-foreground">{r.resource}</td>
                              <td className="py-1">
                                <Badge tone={DECISION_TONES[r.decision] ?? "neutral"}>
                                  {r.decision}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : null}
                    {p.problems.length > 0 ? (
                      <p className="mt-1 text-xs text-red-300">{p.problems.join("; ")}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="mb-3 text-sm font-semibold">Evaluation history</h2>
            {history.state === "loading" ? (
              <Loading label="Loading history…" />
            ) : history.state === "error" ? (
              <ErrorState message={history.error ?? "Unknown error"} onRetry={history.reload} />
            ) : !history.data || history.data.evaluations.length === 0 ? (
              <EmptyState title="No evaluations recorded" hint="Evaluate an action above." />
            ) : (
              <ul className="divide-y divide-border text-sm">
                {history.data.evaluations.map((e) => (
                  <li key={e.evaluation_id} className="flex items-center justify-between gap-3 py-2.5">
                    <div>
                      <span className="font-mono text-xs">{e.policy_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {" "}
                        · {e.action} on {e.resource}
                      </span>
                    </div>
                    <Badge tone={DECISION_TONES[e.decision] ?? "neutral"}>{e.decision}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </PageShell>
  );
}
