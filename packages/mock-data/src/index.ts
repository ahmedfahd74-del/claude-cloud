import type {
  AllocationResponse,
  Candidate,
  CandidateScoreBreakdown,
  ChallengeReport,
  CompanyStateSummary,
  ExposureSummary,
  MarketBarsResponse,
  MarketQuoteResponse,
  MemoryRecord,
  MemorySearchResponse,
  OpportunityScanResponse,
  OverviewMetrics,
  PaperOrderResponse,
  PodPerformanceSummary,
  Position,
  PolicyQueueItem,
  RecentDecision,
  ReviewReportV2,
  RiskReview,
  SettingsVisibility,
  JournalEntry,
  SourceHealth,
  SourceHealthResponse,
  TradeManagementEvent,
} from "@trading-os/contracts";

export const mockCompanyState: CompanyStateSummary = {
  state: "YELLOW",
  reasonCode: "SOURCE_STALE_WARNING",
  newTradeAllowed: true,
  sizeHaircut: 0.35,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockOverviewMetrics: OverviewMetrics = {
  activePods: 4,
  portfolioValue: 103204.44,
  dailyPnl: -127.11,
  trustGrade: "B",
  marketRegime: "neutral",
};

export const mockCandidateList: Candidate[] = [
  {
    candidateId: "LRP-AAPL-001",
    podName: "LiquidityReversalPod",
    setupFamily: "liquidity_reversal",
    asset: "AAPL",
    direction: "LONG",
    timeframe: "4H",
    entryZoneLow: 174,
    entryZoneHigh: 175.2,
    hardStop: 171.6,
    target1: 178.1,
    target2: 181.5,
    holdingHorizon: "2-5 days",
    thesis: "Sweep-and-reclaim structure with improving momentum.",
    invalidation: "Fails to hold reclaimed liquidity pocket.",
    requiresHumanReview: true,
    discoveredAt: "2026-04-12T03:00:00.000Z",
    status: "APPROVED",
    trustGrade: "B",
    setupQuality: 0.78,
    regimeFit: 0.71,
    executionQualityForecast: 0.67,
    dataConfidence: 0.82,
  },
  {
    candidateId: "CPP-BTCUSD-001",
    podName: "ContinuationPullbackPod",
    setupFamily: "continuation_pullback",
    asset: "BTCUSD",
    direction: "SHORT",
    timeframe: "1H",
    entryZoneLow: 181.3,
    entryZoneHigh: 182.2,
    hardStop: 183.1,
    target1: 179.6,
    target2: 178.2,
    holdingHorizon: "8-24 hours",
    thesis: "Trend continuation after weak pullback rejection.",
    invalidation: "Break and hold above pullback pivot.",
    requiresHumanReview: false,
    discoveredAt: "2026-04-12T03:00:30.000Z",
    status: "RISK_REVIEW",
    trustGrade: "B",
    setupQuality: 0.74,
    regimeFit: 0.69,
    executionQualityForecast: 0.72,
    dataConfidence: 0.77,
  },
];

export const mockRankedCandidateBoard: CandidateScoreBreakdown[] = [
  {
    candidateId: "LRP-AAPL-001",
    setupQuality: 0.78,
    regimeFit: 0.71,
    dataConfidence: 0.82,
    executionQuality: 0.67,
    portfolioFit: 0.8,
    historicalExpectancy: 0.65,
    fragility: 0.3,
    finalScore: 0.603,
    rankInBatch: 1,
  },
  {
    candidateId: "CPP-BTCUSD-001",
    setupQuality: 0.74,
    regimeFit: 0.69,
    dataConfidence: 0.77,
    executionQuality: 0.72,
    portfolioFit: 0.75,
    historicalExpectancy: 0.65,
    fragility: 0.15,
    finalScore: 0.618,
    rankInBatch: 2,
  },
];

export const mockCandidateDetail: Candidate = mockCandidateList[0];

export const mockChallengeReport: ChallengeReport = {
  candidateId: "LRP-AAPL-001",
  decision: "PASS",
  confidence: 0.74,
  challengeSummary: "Candidate passed challenger checks.",
  riskFlags: [],
};

export const mockRiskReview: RiskReview = {
  candidateId: "LRP-AAPL-001",
  outcome: "APPROVE",
  reason: "meets initial hard rules",
  sizeAdjustment: 1,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockAllocationResult: AllocationResponse = {
  ok: true,
  candidateId: "LRP-AAPL-001",
  decision: "ALLOCATE",
  approvedSizeUsd: 4200,
  tradeRiskPct: 0.0042,
  sizingMultiplier: 0.84,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockScanResults: OpportunityScanResponse = {
  scannedAssets: ["AAPL", "BTCUSD"],
  candidateCount: mockCandidateList.length,
  candidates: mockCandidateList,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockExposureSummary: ExposureSummary = {
  byAsset: { AAPL: 1780, BTCUSD: 910 },
  bySleeve: { LiquidityReversalPod: 1780, ContinuationPullbackPod: 910 },
  byDirection: { LONG: 1780, SHORT: 910 },
  byAssetClass: { equity: 1780, crypto: 910 },
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockOpenPositions: Position[] = [
  {
    positionId: 1,
    orderId: 1001,
    symbol: "AAPL",
    direction: "LONG",
    podName: "LiquidityReversalPod",
    qty: 10,
    avgPrice: 175.5,
    marketValue: 1780,
    status: "ACTIVE",
  },
];

export const mockExecutionLog: TradeManagementEvent[] = [
  {
    timestamp: "2026-04-12T04:15:00.000Z",
    eventType: "ORDER_FILLED",
    details: "Paper fill simulated immediately",
    orderId: 1001,
  },
  {
    timestamp: "2026-04-12T04:15:01.000Z",
    eventType: "POSITION_ACTIVE",
    details: "Position opened from paper fill",
    positionId: 1,
    orderId: 1001,
  },
];

export const mockPaperOrderResponse: PaperOrderResponse = {
  ok: true,
  order: {
    orderId: 1001,
    candidateId: "LRP-AAPL-001",
    symbol: "AAPL",
    direction: "LONG",
    podName: "LiquidityReversalPod",
    qty: 10,
    price: 175.5,
    status: "FILLED",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
  position: mockOpenPositions[0],
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockSourceHealth: SourceHealth[] = [
  {
    source: "research_primary",
    status: "ok",
    latencyMs: 95,
    staleSeconds: 8,
    trustGrade: "A",
    updatedAt: "2026-04-12T02:00:00.000Z",
  },
  {
    source: "fallback_source",
    status: "degraded",
    latencyMs: 210,
    staleSeconds: 210,
    trustGrade: "C",
    updatedAt: "2026-04-12T01:57:00.000Z",
  },
];

export const mockMarketBars: MarketBarsResponse = {
  symbol: "AAPL",
  interval: "1m",
  bars: [
    { ts: "2026-04-12T11:30:00.000Z", open: 100, high: 101, low: 99.5, close: 100.5, volume: 1000 },
    { ts: "2026-04-12T11:31:00.000Z", open: 100.5, high: 101.2, low: 100.2, close: 101.0, volume: 1200 },
  ],
  source: "research_primary",
  trustGrade: "A",
  validation: {
    freshnessOk: true,
    staleDetected: false,
    conflictDetected: false,
    trustGrade: "A",
    sourceHealth: {
      source: "research_primary",
      status: "ok",
      latencyMs: 95,
      staleSeconds: 8,
      trustGrade: "A",
      updatedAt: "2026-04-12T11:31:05.000Z",
    },
  },
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockMarketQuote: MarketQuoteResponse = {
  symbol: "AAPL",
  quote: { ts: "2026-04-12T11:31:00.000Z", bid: 100.9, ask: 101.1, last: 101.0 },
  source: "research_primary",
  trustGrade: "A",
  validation: mockMarketBars.validation,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockSourceHealthResponse: SourceHealthResponse = {
  checks: mockSourceHealth,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockRecentDecisions: RecentDecision[] = [
  {
    id: "dec-001",
    type: "governance",
    summary: "Transitioned GREEN → YELLOW due to fallback staleness.",
    timestamp: "2026-04-12T01:58:00.000Z",
  },
  {
    id: "dec-002",
    type: "allocation",
    summary: "Allocated $4,200 risk budget to LRP-AAPL-001 in paper mode.",
    timestamp: "2026-04-12T04:16:00.000Z",
  },
];

export const mockServiceHealthCards = [
  { service: "market-data", status: "ok", latencyMs: 95 },
  { service: "validation", status: "ok", latencyMs: 40 },
  { service: "governance", status: "ok", latencyMs: 25 },
];

export const mockKillSwitchHistory = [
  { id: "kill-001", reasonCode: "MANUAL_OVERRIDE", note: "Operator drill", createdAt: "2026-04-10T17:10:00.000Z" },
];

export const mockTransitionLog = [
  {
    fromState: "GREEN",
    toState: "YELLOW",
    reasonCode: "SOURCE_STALE_WARNING",
    note: "fallback_source stale > 180s",
    createdAt: "2026-04-12T01:58:00.000Z",
  },
];

export const mockJournalEntries: JournalEntry[] = [
  {
    journalId: 1,
    journalType: "POST_TRADE_SUMMARY",
    asset: "AAPL",
    pod: "LiquidityReversalPod",
    summary: "Followed plan, managed partial exit correctly.",
    candidateId: "LRP-AAPL-001",
    positionId: 1,
    paperOrderId: 1001,
    tags: ["discipline", "risk-management"],
    createdAt: "2026-04-12T05:05:00.000Z",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
];

export const mockMemoryRecords: MemoryRecord[] = [
  {
    memoryId: 1,
    memoryType: "EPISODIC",
    asset: "AAPL",
    pod: "LiquidityReversalPod",
    regime: "YELLOW",
    setupFamily: "liquidity_reversal",
    tags: ["reclaim", "momentum"],
    summary: "Reclaims perform better when first pullback holds VWAP.",
    createdAt: "2026-04-12T05:10:00.000Z",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
  {
    memoryId: 2,
    memoryType: "SEMANTIC",
    asset: "BTCUSD",
    pod: "ContinuationPullbackPod",
    regime: "YELLOW",
    setupFamily: "continuation_pullback",
    tags: ["trend", "volatility"],
    summary: "Short continuation quality drops when spread widens > 2x median.",
    createdAt: "2026-04-12T05:15:00.000Z",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
];

export const mockMemorySearchResults: MemorySearchResponse = {
  ok: true,
  results: mockMemoryRecords,
  count: mockMemoryRecords.length,
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};

export const mockReviewReports: ReviewReportV2[] = [
  {
    reviewId: 1,
    positionId: 1,
    candidateId: "LRP-AAPL-001",
    asset: "AAPL",
    pod: "LiquidityReversalPod",
    processScore: 0.82,
    executionScore: 0.76,
    outcomeScore: 0.71,
    reviewSummary: "Good process adherence; improve entry patience near zone high.",
    createdAt: "2026-04-12T05:20:00.000Z",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
];

export const mockPodPerformance: PodPerformanceSummary[] = [
  {
    pod: "LiquidityReversalPod",
    regime: "YELLOW",
    timeframe: "4H",
    assetClass: "equity",
    tradesCount: 12,
    winRate: 0.667,
    avgOutcomeScore: 0.694,
    computedAt: "2026-04-12T05:25:00.000Z",
  },
];

export const mockPolicyQueue: PolicyQueueItem[] = [
  {
    proposalId: 1,
    proposalType: "RISK_THRESHOLD",
    title: "Tighten drawdown clamp in YELLOW",
    rationale: "Recent review cadence suggests slightly lower tolerance.",
    status: "PENDING_REVIEW",
    proposedBy: "review-engine",
    createdAt: "2026-04-12T05:30:00.000Z",
    paperTradingOnly: true,
    liveExecutionEnabled: false,
  },
];

export const mockSettingsVisibility: SettingsVisibility = {
  companyPolicyDefaults: {
    paperTradingOnly: true,
    liveExecutionEnabled: false,
    defaultState: "GREEN",
    defaultSizeHaircut: 0,
  },
  riskDefaults: {
    baseRiskPct: 0.005,
    maxSingleTradeRiskPct: 0.01,
    allocationDecisionRequired: true,
  },
  dataRouting: {
    sourceOrder: ["research_primary", "fallback_source", "cache_source", "crypto_exchange_native"],
    conflictPolicy: "prefer_primary_then_fallback",
  },
  modelRouting: {
    rankingModel: "ranking_v1_weighted",
    riskReviewModel: "risk_review_rules_v1",
    executionModel: "paper_execution_sim_v1",
  },
  pods: [
    { pod: "LiquidityReversalPod", status: "ACTIVE", trustGrade: "B", models: ["lrp-v1"] },
    { pod: "ContinuationPullbackPod", status: "ACTIVE", trustGrade: "B", models: ["cpp-v1"] },
  ],
  paperTradingOnly: true,
  liveExecutionEnabled: false,
};
