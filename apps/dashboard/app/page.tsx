import { PageHeader } from "@/components/ui";
import { ApiStatus } from "@/components/api-status";
import { OverviewStats } from "@/components/overview-stats";

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        description="Live security posture for your AI agents, backed by the local AgentFence API and SQLite scan history."
      />
      <ApiStatus />
      <OverviewStats />
    </div>
  );
}
