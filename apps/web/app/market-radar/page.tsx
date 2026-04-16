import { Card, EmptyState, ErrorState } from "@trading-os/ui";

import { loadMarketRadarData } from "../../lib/api";

export default async function MarketRadarPage() {
  const { sourceHealth, bars, quote, degraded } = await loadMarketRadarData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Market Radar</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Market radar is using fallback data." />}

      <Card title="Source Health">
        <ul>
          {sourceHealth.map((s: any) => (
            <li key={s.source}>{s.source}: {s.status} ({s.trustGrade}) {s.latencyMs}ms</li>
          ))}
        </ul>
      </Card>

      <Card title="Latest Quote">
        <p>Symbol: {quote.symbol}</p>
        <p>Last: {(quote as any).quote?.last ?? "n/a"}</p>
        <p>Trust: {(quote as any).trustGrade ?? "n/a"}</p>
      </Card>

      <Card title="Recent Bars">
        {(bars as any).bars?.length ? (
          <ul>
            {(bars as any).bars.slice(0, 5).map((b: any, idx: number) => (
              <li key={`${b.ts}-${idx}`}>{String(b.ts)} O:{String(b.open)} H:{String(b.high)} L:{String(b.low)} C:{String(b.close)}</li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No bars" message="No market bars available." />
        )}
      </Card>
    </main>
  );
}
