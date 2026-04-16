import { Card, ErrorState } from "@trading-os/ui";

import { loadReviewDetail } from "../../../../lib/api";

export default async function ReviewDetailPage({ params }: { params: { positionId: string } }) {
  const positionId = Number(params.positionId);
  const { review, degraded } = await loadReviewDetail(positionId);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Review Detail: Position {params.positionId}</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Showing fallback review detail." />}

      <Card title="Summary">
        <p>{review.reviewSummary}</p>
      </Card>

      <Card title="Scores">
        <p>Process Score: {review.processScore}</p>
        <p>Execution Score: {review.executionScore}</p>
        <p>Outcome Score: {review.outcomeScore}</p>
      </Card>

      <Card title="Linked Refs">
        <p>Asset: {review.asset ?? "n/a"}</p>
        <p>Pod: {review.pod ?? "n/a"}</p>
        <p>Candidate: {review.candidateId ?? "n/a"}</p>
        <p>Position: {review.positionId ?? "n/a"}</p>
      </Card>
    </main>
  );
}
