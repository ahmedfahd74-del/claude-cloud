import { Card, ErrorState } from "@trading-os/ui";

import { loadCandidateDetail } from "../../../lib/api";

export default async function CandidateDetailPage({ params }: { params: { candidateId: string } }) {
  const { detail, degraded } = await loadCandidateDetail(params.candidateId);
  const candidate = detail.candidate;

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Candidate Detail: {params.candidateId}</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Showing fallback candidate detail data." />}

      <Card title="Context Summary">
        <p>{candidate.podName} / {candidate.setupFamily}</p>
        <p>{candidate.asset} {candidate.direction} {candidate.timeframe}</p>
        <p>Status: {candidate.status}</p>
        <p>Trust: {candidate.trustGrade}</p>
      </Card>

      <Card title="Thesis">
        <p>{candidate.thesis}</p>
        <p><strong>Invalidation:</strong> {candidate.invalidation}</p>
      </Card>

      <Card title="Challenge">
        <p>Decision: {detail.challenge?.decision ?? "N/A"}</p>
        <p>Confidence: {detail.challenge?.confidence ?? "N/A"}</p>
        <p>{detail.challenge?.challengeSummary ?? "No challenge report yet."}</p>
      </Card>

      <Card title="Risk">
        <p>Outcome: {detail.riskReview?.outcome ?? "N/A"}</p>
        <p>Reason: {detail.riskReview?.reason ?? "N/A"}</p>
      </Card>

      <Card title="History / Similar (Placeholder)">
        <p>Placeholder: similar setups and historical analogs will be connected in a future phase.</p>
      </Card>
    </main>
  );
}
