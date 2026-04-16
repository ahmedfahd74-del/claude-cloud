import { Card, ErrorState } from "@trading-os/ui";

import { loadExecutionData } from "../../lib/api";

export default async function ExecutionPage() {
  const { positions, paperOrder, events, degraded } = await loadExecutionData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Execution (Paper)</h1>
      <ErrorState title="Paper-Only Warning" message="Live execution adapters are disabled in this environment." />
      {degraded && <ErrorState title="Degraded Mode" message="Execution data using fallback payloads." />}

      <Card title="Pending / Paper Orders">
        <p>Last order: #{paperOrder?.order?.orderId ?? "n/a"}</p>
        <p>Status: {paperOrder?.order?.status ?? "n/a"}</p>
      </Card>

      <Card title="Active Positions">
        <ul>
          {positions.map((p: any) => (
            <li key={p.positionId}>
              {p.symbol} {p.direction} | {p.status} | qty {p.qty}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Management Event Log">
        <ul>
          {events.map((e: any, idx: number) => (
            <li key={`${e.timestamp}-${idx}`}>{e.timestamp} [{e.eventType}] {e.details}</li>
          ))}
        </ul>
      </Card>

      <Card title="Fill Quality (Placeholder)">
        <p>Placeholder summary: slippage, latency, and adverse selection metrics will be added in a later phase.</p>
      </Card>
    </main>
  );
}
