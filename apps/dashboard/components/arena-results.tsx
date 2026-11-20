"use client";

import { Badge } from "@/components/ui";
import { Card } from "@/components/ui";
import type { ArenaRunDto } from "@/lib/api";

/** Renders Arena run results: pass/fail summary, score, and per-scenario detail. */
export function RunResults({ run }: { run: ArenaRunDto }) {
  const total = run.results.length;
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <Badge tone={run.passed === total ? "success" : "critical"}>
          {run.passed}/{total} passed
        </Badge>
        <span className="text-muted-foreground">
          Score: {Math.round((run.score ?? 0) * 100)}%
        </span>
        {run.run_id ? (
          <span className="font-mono text-xs text-muted-foreground">
            run {run.run_id.slice(0, 8)}
          </span>
        ) : null}
      </div>
      <div className="space-y-2">
        {run.results.map((r) => (
          <div key={r.scenario} className="rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={r.passed ? "success" : "critical"}>
                {r.passed ? "PASS" : "FAIL"}
              </Badge>
              <span className="font-mono text-xs font-medium">{r.scenario}</span>
              <span className="text-xs text-muted-foreground">
                expected: {r.expected} · actual: {r.actual}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{r.explanation}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
