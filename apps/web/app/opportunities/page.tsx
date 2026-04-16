import Link from "next/link";

import { Badge, Card, EmptyState, ErrorState, LoadingState } from "@trading-os/ui";

import { loadOpportunitiesData } from "../../lib/api";

type SearchProps = {
  searchParams?: Promise<{
    pod?: string;
    trust?: string;
  }>;
};

export default async function OpportunitiesPage({ searchParams }: SearchProps) {
  const resolvedParams = await searchParams;
  const filters = {
    pod: resolvedParams?.pod,
    trust: resolvedParams?.trust,
  };

  const { candidates, degraded } = await loadOpportunitiesData(filters);

  if (!candidates) return <LoadingState label="Loading opportunities..." />;

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Opportunities</h1>
      {degraded && <ErrorState title="Degraded Mode" message="Backend unavailable. Showing mock candidate pipeline." />}

      <Card title="Filters">
        <div style={{ display: "flex", gap: 16 }}>
          <span>pod={filters.pod ?? "ALL"}</span>
          <span>trust={filters.trust ?? "ALL"}</span>
        </div>
      </Card>

      {candidates.length === 0 ? (
        <EmptyState title="No candidates" message="Try broadening filters or scanning more assets." />
      ) : (
        <Card title="Candidate Table">
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Candidate</th>
                <th align="left">Pod</th>
                <th align="left">Trust</th>
                <th align="left">Scores</th>
                <th align="left">Action</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={candidate.candidateId}>
                  <td>{candidate.asset}</td>
                  <td>
                    <Badge label={candidate.podName} />
                  </td>
                  <td>
                    <Badge label={`Trust ${candidate.trustGrade}`} />
                  </td>
                  <td>
                    <span style={{ border: "1px solid #ddd", borderRadius: 8, padding: "2px 6px", marginRight: 4 }}>
                      SQ {candidate.setupQuality}
                    </span>
                    <span style={{ border: "1px solid #ddd", borderRadius: 8, padding: "2px 6px", marginRight: 4 }}>
                      RF {candidate.regimeFit}
                    </span>
                    <span style={{ border: "1px solid #ddd", borderRadius: 8, padding: "2px 6px" }}>
                      DQ {candidate.dataConfidence}
                    </span>
                  </td>
                  <td>
                    <Link href={`/opportunities/${candidate.candidateId}`}>View Detail</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </main>
  );
}
