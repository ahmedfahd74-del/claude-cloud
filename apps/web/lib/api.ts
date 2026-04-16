import {
  mockAllocationResult,
  mockCandidateDetail,
  mockCandidateList,
  mockChallengeReport,
  mockCompanyState,
  mockExecutionLog,
  mockExposureSummary,
  mockKillSwitchHistory,
  mockMarketBars,
  mockMarketQuote,
  mockOpenPositions,
  mockOverviewMetrics,
  mockPaperOrderResponse,
  mockPodPerformance,
  mockPolicyQueue,
  mockRankedCandidateBoard,
  mockRecentDecisions,
  mockReviewReports,
  mockRiskReview,
  mockScanResults,
  mockSettingsVisibility,
  mockServiceHealthCards,
  mockSourceHealth,
  mockTransitionLog,
  mockMemorySearchResults,
} from "@trading-os/mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function safeFetch<T>(path: string, fallback: T, init?: RequestInit): Promise<{ data: T; degraded: boolean }> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    const data = (await response.json()) as T;
    return { data, degraded: false };
  } catch {
    return { data: fallback, degraded: true };
  }
}

export async function loadOverviewData() {
  const [state, sourceHealth, ranked, exposure] = await Promise.all([
    safeFetch("/api/v1/governance/state", mockCompanyState),
    safeFetch("/api/v1/market/source-health", { checks: mockSourceHealth }),
    safeFetch("/api/v1/portfolio/rank", { ranked: mockRankedCandidateBoard }, { method: "POST", body: JSON.stringify({}), headers: { "content-type": "application/json" } }),
    safeFetch("/api/v1/portfolio/exposure", mockExposureSummary),
  ]);

  return {
    companyState: state.data,
    sourceHealth: (sourceHealth.data as { checks: typeof mockSourceHealth }).checks,
    rankedCandidates: (ranked.data as { ranked: typeof mockRankedCandidateBoard }).ranked,
    metrics: mockOverviewMetrics,
    decisions: mockRecentDecisions,
    exposure: exposure.data,
    degraded: state.degraded || sourceHealth.degraded || ranked.degraded || exposure.degraded,
  };
}

export async function loadGovernanceData() {
  const state = await safeFetch("/api/v1/governance/state", {
    ...mockCompanyState,
    serviceHealth: mockServiceHealthCards,
    transitionLog: mockTransitionLog,
    killSwitchEvents: mockKillSwitchHistory,
  });

  return { state: state.data, degraded: state.degraded };
}

export async function loadOpportunitiesData(filters?: { pod?: string; trust?: string }) {
  const candidatesResponse = await safeFetch("/api/v1/opportunities/candidates", { candidates: mockCandidateList });
  let candidates = (candidatesResponse.data as { candidates: typeof mockCandidateList }).candidates;

  if (filters?.pod) candidates = candidates.filter((c) => c.podName === filters.pod);
  if (filters?.trust) candidates = candidates.filter((c) => c.trustGrade === filters.trust);

  return {
    candidates,
    degraded: candidatesResponse.degraded,
    scanSummary: mockScanResults,
  };
}

export async function loadCandidateDetail(candidateId: string) {
  const detail = await safeFetch(`/api/v1/opportunities/candidates/${candidateId}`, {
    ok: true,
    candidate: mockCandidateDetail,
    challenge: mockChallengeReport,
    riskReview: mockRiskReview,
  });

  return {
    detail: detail.data as any,
    degraded: detail.degraded,
  };
}

export async function loadPortfolioData() {
  const [exposure, positions, ranked] = await Promise.all([
    safeFetch("/api/v1/portfolio/exposure", mockExposureSummary),
    safeFetch("/api/v1/execution/positions/open", { positions: mockOpenPositions }),
    safeFetch("/api/v1/portfolio/rank", { ranked: mockRankedCandidateBoard }, { method: "POST", body: JSON.stringify({}), headers: { "content-type": "application/json" } }),
  ]);

  return {
    exposure: exposure.data,
    positions: (positions.data as { positions: typeof mockOpenPositions }).positions,
    ranked: (ranked.data as { ranked: typeof mockRankedCandidateBoard }).ranked,
    allocation: mockAllocationResult,
    degraded: exposure.degraded || positions.degraded || ranked.degraded,
  };
}

export async function loadExecutionData() {
  const [positions, order, events] = await Promise.all([
    safeFetch("/api/v1/execution/positions/open", { positions: mockOpenPositions }),
    safeFetch("/api/v1/execution/orders/paper", mockPaperOrderResponse, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ candidateId: "LRP-AAPL-001", symbol: "AAPL", direction: "LONG", podName: "LiquidityReversalPod", qty: 10, price: 175.5 }),
    }),
    safeFetch("/api/v1/execution/positions/manage", { events: mockExecutionLog }, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ positionId: 1, action: "partial_exit" }),
    }),
  ]);

  return {
    positions: (positions.data as { positions: typeof mockOpenPositions }).positions,
    paperOrder: order.data,
    events: (events.data as { events: typeof mockExecutionLog }).events ?? mockExecutionLog,
    degraded: positions.degraded || order.degraded || events.degraded,
  };
}

export async function loadMemoryPageData(query = "") {
  const [search, reviews, performance, policyQueue] = await Promise.all([
    safeFetch("/api/v1/memory/search", mockMemorySearchResults, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query }),
    }),
    safeFetch("/api/v1/memory/reviews", { reviews: mockReviewReports, count: mockReviewReports.length }),
    safeFetch("/api/v1/memory/pod-performance", { summaries: mockPodPerformance }),
    safeFetch("/api/v1/memory/policy-queue", { items: mockPolicyQueue, count: mockPolicyQueue.length }),
  ]);

  return {
    memories: (search.data as any).results ?? mockMemorySearchResults.results,
    reviews: (reviews.data as any).reviews ?? mockReviewReports,
    podPerformance: (performance.data as any).summaries ?? mockPodPerformance,
    policyQueue: (policyQueue.data as any).items ?? mockPolicyQueue,
    degraded: search.degraded || reviews.degraded || performance.degraded || policyQueue.degraded,
  };
}

export async function loadReviewDetail(positionId: number) {
  const detail = await safeFetch(`/api/v1/memory/review/${positionId}`, { ok: true, review: mockReviewReports[0] });
  return { review: (detail.data as any).review ?? mockReviewReports[0], degraded: detail.degraded };
}

export async function loadSettingsData() {
  const settings = await safeFetch("/api/v1/settings/visibility", mockSettingsVisibility);
  return { settings: settings.data, degraded: settings.degraded };
}

export async function loadMarketRadarData() {
  const [sourceHealth, bars, quote] = await Promise.all([
    safeFetch("/api/v1/market/source-health", { checks: mockSourceHealth }),
    safeFetch("/api/v1/market/bars", mockMarketBars),
    safeFetch("/api/v1/market/quote", mockMarketQuote),
  ]);

  return {
    sourceHealth: (sourceHealth.data as any).checks ?? mockSourceHealth,
    bars: bars.data,
    quote: quote.data,
    degraded: sourceHealth.degraded || bars.degraded || quote.degraded,
  };
}
