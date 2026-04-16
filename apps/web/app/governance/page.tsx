import { Card, ErrorState } from "@trading-os/ui";

import { loadGovernanceData } from "../../lib/api";

export default async function GovernancePage() {
  const { state, degraded } = await loadGovernanceData();
  const serviceHealth = state.serviceHealth ?? [];
  const killEvents = state.killSwitchEvents ?? [];
  const transitions = state.transitionLog ?? [];

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Governance</h1>
      {(degraded || state.state === "RED" || state.state === "BLACKOUT") && (
        <ErrorState
          title="Warning"
          message={degraded ? "Degraded backend connectivity; showing fallback data." : "System is in restricted mode."}
        />
      )}

      <Card title="Current Company State">
        <p>
          <strong>{state.state}</strong> ({state.reasonCode})
        </p>
        <p>New trade permission: {String(state.newTradeAllowed)}</p>
        <p>Size haircut: {String(state.sizeHaircut)}</p>
      </Card>

      <Card title="Service Health Board">
        <ul>
          {serviceHealth.map((service: { service: string; status: string; latencyMs: number }) => (
            <li key={service.service}>
              {service.service}: {service.status} ({service.latencyMs}ms)
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Kill-Switch History">
        <ul>
          {killEvents.length === 0 && <li>No kill-switch events logged.</li>}
          {killEvents.map((event: { createdAt: string; reasonCode: string }) => (
            <li key={`${event.createdAt}-${event.reasonCode}`}>
              {event.createdAt}: {event.reasonCode}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Audit / State Transition Log">
        <ul>
          {transitions.length === 0 && <li>No transitions recorded yet.</li>}
          {transitions.map(
            (event: { createdAt: string; fromState: string; toState: string; reasonCode: string; note: string }) => (
              <li key={`${event.createdAt}-${event.reasonCode}`}>
                {event.createdAt}: {event.fromState} → {event.toState} ({event.reasonCode}) {event.note}
              </li>
            )
          )}
        </ul>
      </Card>
    </main>
  );
}
