import { Card, ErrorState, StatTile } from "@trading-os/ui";

import { loadMemoryPageData, loadOverviewData } from "../../lib/api";

export default async function OverviewPage() {
  const { companyState, sourceHealth, rankedCandidates, metrics, decisions, exposure, degraded } = await loadOverviewData();
  const { reviews, podPerformance } = await loadMemoryPageData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Overview</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Backend unavailable. Showing cached/mock data." />}

      <Card title="Company State Hero">
        <p>
          State: <strong>{companyState.state}</strong>
        </p>
        <p>Reason: {companyState.reasonCode}</p>
        <p>New trades allowed: {String(companyState.newTradeAllowed)}</p>
        <p>Size haircut: {String(companyState.sizeHaircut)}</p>
      </Card>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <StatTile label="Active Pods" value={metrics.activePods} />
        <StatTile label="Portfolio" value={`$${metrics.portfolioValue.toFixed(2)}`} />
        <StatTile label="Daily PnL" value={`$${metrics.dailyPnl.toFixed(2)}`} />
        <StatTile label="Trust" value={metrics.trustGrade} />
      </div>

      <Card title="Top Opportunity Snapshot (Ranked)">
        <ul>
          {rankedCandidates.map((row: any) => (
            <li key={row.candidateId}>
              #{row.rankInBatch} {row.candidateId} | score {row.finalScore}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Portfolio Exposure Summary">
        <p>By Asset: {JSON.stringify(exposure.byAsset)}</p>
        <p>By Direction: {JSON.stringify(exposure.byDirection)}</p>
      </Card>

      <Card title="Market Condition Summary">
        <p>Regime: {metrics.marketRegime}</p>
        <ul>
          {sourceHealth.map((source) => (
            <li key={source.source}>
              {source.source}: {source.status} ({source.trustGrade})
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Recent Decisions Feed">
        <ul>
          {decisions.map((decision) => (
            <li key={decision.id}>
              [{decision.type}] {decision.summary}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Recent Reviews">
        <ul>
          {reviews.slice(0, 3).map((r: any) => (
            <li key={r.reviewId}>
              {r.asset ?? "n/a"} {r.pod ?? "n/a"} | outcome {r.outcomeScore} | {r.reviewSummary}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Pod Performance Snapshot">
        <ul>
          {podPerformance.slice(0, 3).map((p: any, idx: number) => (
            <li key={`${p.pod}-${idx}`}>
              {p.pod}: trades {p.tradesCount}, winRate {p.winRate}
            </li>
          ))}
        </ul>
      </Card>
    </main>
  );
}
