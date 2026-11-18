"use client";

import { useState } from "react";
import {
  api,
  ApiError,
  type ArenaRunDto,
  type ArenaScenarioDto,
} from "@/lib/api";
import { useApiData } from "@/lib/useApiData";
import { PageHeader, Card, Badge } from "@/components/ui";
import { RunResults } from "@/components/arena-results";
import { ApiStatus } from "@/components/api-status";
import { Loading, ErrorState, EmptyState, PageShell } from "@/components/states";

function ScenarioCatalogue({
  scenarios,
  selected,
  onToggle,
}: {
  scenarios: ArenaScenarioDto[];
  selected: Set<string>;
  onToggle: (name: string) => void;
}) {
  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold">
        Scenario catalogue ({scenarios.length})
      </h2>
      <div className="space-y-2">
        {scenarios.map((s) => (
          <label
            key={s.name}
            className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 hover:bg-accent/40"
          >
            <input
              type="checkbox"
              checked={selected.has(s.name)}
              onChange={() => onToggle(s.name)}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-medium">{s.name}</span>
                <Badge tone="info">{s.expected_decision}</Badge>
                {s.tags.map((t) => (
                  <Badge key={t} tone="neutral">
                    {t}
                  </Badge>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{s.description}</p>
            </div>
          </label>
        ))}
      </div>
    </Card>
  );
}

export default function ArenaPage() {
  const scenarios = useApiData(() => api.arenaScenarios(), []);
  const history = useApiData(() => api.arenaRuns(10), []);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<ArenaRunDto | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [expandedRun, setExpandedRun] = useState<ArenaRunDto | null>(null);

  function toggle(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function runArena() {
    setRunning(true);
    setRunError(null);
    setLastRun(null);
    try {
      const ids = selected.size ? [...selected] : undefined;
      const run = await api.arenaRun(ids);
      setLastRun(run);
      history.reload();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Arena run failed unexpectedly");
    } finally {
      setRunning(false);
    }
  }

  async function openHistoricalRun(runId: string) {
    setExpandedRun(null);
    try {
      setExpandedRun(await api.arenaRunDetail(runId));
    } catch {
      setExpandedRun(null);
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Attack Lab"
        description="Run declarative security scenarios through the deterministic Arena engine. Fixtures are YAML data — nothing is executed and no external systems are contacted."
      />
      <ApiStatus />

      {scenarios.state === "loading" ? (
        <Loading label="Loading scenario catalogue…" />
      ) : scenarios.state === "error" ? (
        <ErrorState message={scenarios.error ?? "Unknown error"} onRetry={scenarios.reload} />
      ) : !scenarios.data || scenarios.data.length === 0 ? (
        <EmptyState title="No scenarios found" hint="Add YAML scenarios under benchmarks/scenarios/." />
      ) : (
        <>
          <ScenarioCatalogue
            scenarios={scenarios.data}
            selected={selected}
            onToggle={toggle}
          />
          <div className="my-4 flex items-center gap-3">
            <button
              onClick={runArena}
              disabled={running}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {running ? "Running…" : selected.size ? `Run ${selected.size} scenario(s)` : "Run all"}
            </button>
            {running ? (
              <span className="text-sm text-muted-foreground">
                Evaluating fixtures against deterministic policies…
              </span>
            ) : null}
          </div>
          {runError ? (
            <div className="mb-4">
              <ErrorState message={runError} onRetry={runArena} />
            </div>
          ) : null}
          {lastRun ? (
            <div className="mb-6">
              <RunResults run={lastRun} />
            </div>
          ) : null}
        </>
      )}

      <Card>
        <h2 className="mb-3 text-sm font-semibold">Historical runs</h2>
        {history.state === "loading" ? (
          <Loading label="Loading run history…" />
        ) : history.state === "error" ? (
          <ErrorState message={history.error ?? "Unknown error"} onRetry={history.reload} />
        ) : !history.data || history.data.runs.length === 0 ? (
          <EmptyState title="No arena runs recorded" hint="Run the suite above to create history." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">Run</th>
                  <th className="pb-3 pr-4 font-medium">When (UTC)</th>
                  <th className="pb-3 pr-4 font-medium">Scenarios</th>
                  <th className="pb-3 pr-4 font-medium">Passed</th>
                  <th className="pb-3 pr-4 font-medium">Score</th>
                  <th className="pb-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {history.data.runs.map((r) => (
                  <tr key={r.run_id} className="border-b last:border-0">
                    <td className="py-2.5 pr-4 font-mono text-xs">{r.run_id.slice(0, 8)}</td>
                    <td className="py-2.5 pr-4 text-xs text-muted-foreground">{r.created_at}</td>
                    <td className="py-2.5 pr-4">{r.scenario_count}</td>
                    <td className="py-2.5 pr-4">
                      <Badge tone={r.failed === 0 ? "success" : "critical"}>
                        {r.passed}/{r.scenario_count}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4">{Math.round(r.score * 100)}%</td>
                    <td className="py-2.5">
                      <button
                        className="text-xs text-primary hover:underline"
                        onClick={() => openHistoricalRun(r.run_id)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {expandedRun ? (
          <div className="mt-4">
            <RunResults run={expandedRun} />
          </div>
        ) : null}
      </Card>
    </PageShell>
  );
}
