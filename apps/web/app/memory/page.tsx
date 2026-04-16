import Link from "next/link";

import { Card, EmptyState, ErrorState } from "@trading-os/ui";

import { loadMemoryPageData } from "../../lib/api";

export default async function MemoryPage() {
  const { memories, reviews, podPerformance, policyQueue, degraded } = await loadMemoryPageData();

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Memory & Learning</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Using fallback memory/review data." />}

      <Card title="Memory Search">
        <p>Local-first memory records (episodic / semantic / procedural).</p>
        {memories.length === 0 ? (
          <EmptyState title="No memory records" message="Store a memory entry to populate this list." />
        ) : (
          <ul>
            {memories.map((m: any) => (
              <li key={m.memoryId}>
                [{m.memoryType}] {m.asset ?? "n/a"} / {m.pod ?? "n/a"}: {m.summary}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Review List">
        {reviews.length === 0 ? (
          <EmptyState title="No reviews" message="Generate reviews from the memory API." />
        ) : (
          <ul>
            {reviews.map((r: any) => (
              <li key={r.reviewId}>
                <Link href={`/memory/reviews/${r.positionId ?? 0}`}>
                  #{r.reviewId} {r.asset ?? "n/a"} {r.pod ?? "n/a"}
                </Link>{" "}
                | process {r.processScore} / exec {r.executionScore} / outcome {r.outcomeScore}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Semantic Insights Board">
        <ul>
          {memories.filter((m: any) => m.memoryType === "SEMANTIC").map((m: any) => (
            <li key={`semantic-${m.memoryId}`}>{m.summary}</li>
          ))}
        </ul>
      </Card>

      <Card title="Pod Performance">
        <ul>
          {podPerformance.map((p: any, idx: number) => (
            <li key={`${p.pod}-${idx}`}>
              {p.pod} | trades {p.tradesCount} | winRate {p.winRate} | avgOutcome {p.avgOutcomeScore}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Policy Queue (Review-only)">
        <ul>
          {policyQueue.map((item: any) => (
            <li key={item.proposalId}>
              [{item.status}] {item.title} — {item.rationale}
            </li>
          ))}
        </ul>
      </Card>
    </main>
  );
}
