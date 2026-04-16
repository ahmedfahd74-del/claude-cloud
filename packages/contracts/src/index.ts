export type TrustGrade = "A" | "B" | "C" | "D" | "E";
export type CompanyState = "GREEN" | "YELLOW" | "RED" | "BLACKOUT";

export interface Candidate {
  candidateId: string;
  podName: string;
  setupFamily: string;
  asset: string;
  direction: "LONG" | "SHORT";
  timeframe: string;
  entryZoneLow: number;
  entryZoneHigh: number;
  hardStop: number;
  target1: number;
  target2: number;
  holdingHorizon: string;
  thesis: string;
  invalidation: string;
  requiresHumanReview: boolean;
  discoveredAt: string;
  status: "NEW" | "CHALLENGED" | "RISK_REVIEW" | "APPROVED" | "REDUCED" | "REJECTED" | "HOLD";
  trustGrade: TrustGrade;
  setupQuality: number;
  regimeFit: number;
  executionQualityForecast: number;
  dataConfidence: number;
}

export interface CandidateScoreBreakdown {
  candidateId: string;
  setupQuality: number;
  regimeFit: number;
  dataConfidence: number;
  executionQuality: number;
  portfolioFit: number;
  historicalExpectancy: number;
  fragility: number;
  finalScore: number;
  rankInBatch: number;
}

export interface RankingRequest {
  candidateIds?: string[];
}

export interface RankingResponse {
  ranked: CandidateScoreBreakdown[];
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface ChallengeReport {
  candidateId: string;
  decision: "PASS" | "CHALLENGE" | "BLOCK";
  confidence: number;
  challengeSummary: string;
  riskFlags: string[];
}

export interface RiskReview {
  candidateId: string;
  outcome: "APPROVE" | "REDUCE" | "REJECT" | "HOLD";
  reason: string;
  sizeAdjustment: number;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface AllocationRequest {
  candidateId: string;
}

export interface AllocationResponse {
  ok: boolean;
  candidateId?: string;
  decision: "ALLOCATE" | "REJECT";
  approvedSizeUsd?: number;
  tradeRiskPct?: number;
  sizingMultiplier?: number;
  reason?: string;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface ExposureSummary {
  byAsset: Record<string, number>;
  bySleeve: Record<string, number>;
  byDirection: Record<string, number>;
  byAssetClass: Record<string, number>;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface OpportunityScanRequest {
  assets: string[];
}

export interface OpportunityScanResponse {
  scannedAssets: string[];
  candidateCount: number;
  candidates: Candidate[];
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface PaperOrderRequest {
  candidateId: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  podName: string;
  qty: number;
  price: number;
}

export interface Position {
  positionId: number;
  orderId: number;
  symbol: string;
  direction: "LONG" | "SHORT";
  podName: string;
  qty: number;
  avgPrice: number;
  marketValue: number;
  status:
    | "PENDING_ENTRY"
    | "PARTIALLY_FILLED"
    | "FILLED"
    | "ACTIVE"
    | "PARTIAL_EXIT_TAKEN"
    | "STOPPED"
    | "TARGET_HIT"
    | "FLAT"
    | "CANCELLED";
}

export interface PaperOrderResponse {
  ok: boolean;
  order: {
    orderId: number;
    candidateId: string;
    symbol: string;
    direction: "LONG" | "SHORT";
    podName: string;
    qty: number;
    price: number;
    status: string;
    paperTradingOnly: true;
    liveExecutionEnabled: false;
  };
  position: Position;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface TradeManagementEvent {
  timestamp: string;
  eventType: string;
  details: string;
  positionId?: number;
  orderId?: number;
}

export interface CompanyStateSummary {
  state: CompanyState;
  reasonCode: string;
  newTradeAllowed: boolean;
  sizeHaircut: number;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface SourceHealth {
  source: string;
  status: "ok" | "degraded" | "down";
  latencyMs: number;
  staleSeconds: number;
  trustGrade: TrustGrade;
  updatedAt: string;
}

export interface MarketValidation {
  freshnessOk: boolean;
  staleDetected: boolean;
  conflictDetected: boolean;
  trustGrade: TrustGrade | string;
  sourceHealth: SourceHealth;
}

export interface MarketBarsResponse {
  symbol: string;
  interval: string;
  bars: Array<Record<string, unknown>>;
  source: string;
  trustGrade: TrustGrade | string;
  validation: MarketValidation;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface MarketQuoteResponse {
  symbol: string;
  quote: Record<string, unknown>;
  source: string;
  trustGrade: TrustGrade | string;
  validation: MarketValidation;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface SourceHealthResponse {
  checks: SourceHealth[];
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface OverviewMetrics {
  activePods: number;
  portfolioValue: number;
  dailyPnl: number;
  trustGrade: TrustGrade;
  marketRegime: "risk_on" | "neutral" | "risk_off";
}

export interface RecentDecision {
  id: string;
  type: "allocation" | "risk" | "governance";
  summary: string;
  timestamp: string;
}

export interface JournalWriteRequest {
  journalType: "CANDIDATE_NOTE" | "POSITION_NOTE" | "POST_TRADE_SUMMARY";
  summary: string;
  asset?: string;
  pod?: string;
  candidateId?: string;
  positionId?: number;
  paperOrderId?: number;
  tags?: string[];
}

export interface JournalEntry {
  journalId: number;
  journalType: JournalWriteRequest["journalType"];
  asset?: string;
  pod?: string;
  summary: string;
  candidateId?: string;
  positionId?: number;
  paperOrderId?: number;
  tags: string[];
  createdAt: string;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface MemoryRecord {
  memoryId: number;
  memoryType: "EPISODIC" | "SEMANTIC" | "PROCEDURAL";
  asset?: string;
  pod?: string;
  regime?: string;
  setupFamily?: string;
  tags: string[];
  summary: string;
  createdAt: string;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface MemorySearchRequest {
  query?: string;
  asset?: string;
  pod?: string;
  regime?: string;
  setupFamily?: string;
}

export interface MemorySearchResponse {
  ok: boolean;
  results: MemoryRecord[];
  count: number;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface ReviewReportV2 {
  reviewId: number;
  positionId?: number;
  candidateId?: string;
  asset?: string;
  pod?: string;
  processScore: number;
  executionScore: number;
  outcomeScore: number;
  reviewSummary: string;
  createdAt: string;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface PodPerformanceSummary {
  pod: string;
  regime: string;
  timeframe: string;
  assetClass: string;
  tradesCount: number;
  winRate: number;
  avgOutcomeScore: number;
  computedAt: string;
}

export interface PolicyQueueItem {
  proposalId: number;
  proposalType: string;
  title: string;
  rationale: string;
  status: "PENDING_REVIEW" | "APPROVED" | "REJECTED";
  proposedBy?: string;
  createdAt: string;
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}

export interface PodRegistryStatus {
  pod: string;
  status: string;
  trustGrade: TrustGrade | string;
  models: string[];
}

export interface SettingsVisibility {
  companyPolicyDefaults: {
    paperTradingOnly: boolean;
    liveExecutionEnabled: boolean;
    defaultState: CompanyState;
    defaultSizeHaircut: number;
  };
  riskDefaults: {
    baseRiskPct: number;
    maxSingleTradeRiskPct: number;
    allocationDecisionRequired: boolean;
  };
  dataRouting: {
    sourceOrder: string[];
    conflictPolicy: string;
  };
  modelRouting: {
    rankingModel: string;
    riskReviewModel: string;
    executionModel: string;
  };
  pods: PodRegistryStatus[];
  paperTradingOnly: true;
  liveExecutionEnabled: false;
}
