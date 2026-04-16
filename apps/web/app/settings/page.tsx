import { Card, EmptyState, ErrorState } from "@trading-os/ui";

import { loadSettingsData } from "../../lib/api";

export default async function SettingsPage() {
  const { settings, degraded } = await loadSettingsData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Settings</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Showing fallback settings visibility data." />}

      <Card title="Company Policy Defaults">
        <p>Paper Trading Only: {String(settings.companyPolicyDefaults.paperTradingOnly)}</p>
        <p>Live Execution Enabled: {String(settings.companyPolicyDefaults.liveExecutionEnabled)}</p>
        <p>Default State: {settings.companyPolicyDefaults.defaultState}</p>
        <p>Default Size Haircut: {settings.companyPolicyDefaults.defaultSizeHaircut}</p>
      </Card>

      <Card title="Risk Defaults">
        <p>Base Risk %: {settings.riskDefaults.baseRiskPct}</p>
        <p>Max Single Trade Risk %: {settings.riskDefaults.maxSingleTradeRiskPct}</p>
        <p>Allocation Required: {String(settings.riskDefaults.allocationDecisionRequired)}</p>
      </Card>

      <Card title="Data Routing">
        <p>Source Order: {settings.dataRouting.sourceOrder.join(" -> ")}</p>
        <p>Conflict Policy: {settings.dataRouting.conflictPolicy}</p>
      </Card>

      <Card title="Model Routing">
        <p>Ranking: {settings.modelRouting.rankingModel}</p>
        <p>Risk Review: {settings.modelRouting.riskReviewModel}</p>
        <p>Execution: {settings.modelRouting.executionModel}</p>
      </Card>

      <Card title="Pods">
        {settings.pods.length === 0 ? (
          <EmptyState title="No pods" message="No pod registry records available." />
        ) : (
          <ul>
            {settings.pods.map((pod: any) => (
              <li key={pod.pod}>
                {pod.pod} | {pod.status} | trust {pod.trustGrade} | models: {pod.models.join(", ")}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </main>
  );
}
