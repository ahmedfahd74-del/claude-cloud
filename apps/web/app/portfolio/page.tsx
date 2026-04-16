import { Card, EmptyState, ErrorState, StatTile } from "@trading-os/ui";

import { loadPortfolioData } from "../../lib/api";

export default async function PortfolioPage() {
  const { exposure, positions, ranked, allocation, degraded } = await loadPortfolioData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Portfolio</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Using fallback portfolio data." />}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <StatTile label="Open Positions" value={positions.length} />
        <StatTile label="Top Allocation" value={`$${allocation.approvedSizeUsd ?? 0}`} />
        <StatTile label="Top Rank Score" value={ranked[0]?.finalScore ?? "n/a"} />
      </div>

      <Card title="Exposure Summary">
        <p><strong>By Asset:</strong> {JSON.stringify(exposure.byAsset)}</p>
        <p><strong>By Sleeve:</strong> {JSON.stringify(exposure.bySleeve)}</p>
        <p><strong>By Direction:</strong> {JSON.stringify(exposure.byDirection)}</p>
      </Card>

      <Card title="Sleeve Overview">
        <ul>
          {Object.entries(exposure.bySleeve ?? {}).map(([sleeve, value]) => (
            <li key={sleeve}>{sleeve}: {String(value)}</li>
          ))}
        </ul>
      </Card>

      {positions.length === 0 ? (
        <EmptyState title="No open positions" message="Run paper execution to create positions." />
      ) : (
        <Card title="Open Positions">
          <table style={{ width: "100%" }}>
            <thead>
              <tr><th align="left">Symbol</th><th align="left">Direction</th><th align="left">Status</th><th align="left">Value</th></tr>
            </thead>
            <tbody>
              {positions.map((p: any) => (
                <tr key={p.positionId}>
                  <td>{p.symbol}</td>
                  <td>{p.direction}</td>
                  <td>{p.status}</td>
                  <td>{p.marketValue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card title="Concentration Warnings">
        <ul>
          <li>Same-asset duplication penalty active in portfolio-fit scoring.</li>
          <li>Same-direction concentration penalty active.</li>
          <li>Same-sleeve crowding penalty active.</li>
        </ul>
      </Card>
    </main>
  );
}
