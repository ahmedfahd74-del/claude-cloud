from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.execution.paper_execution_service import PaperExecutionService
from app.services.governance_service import governance_service
from app.services.market_data.service import MarketDataService
from app.services.memory_service import memory_service
from app.services.opportunities.repository import OpportunityRepository
from app.services.opportunities.service import OpportunityFactoryService
from app.services.portfolio.allocation_service import AllocationService
from app.services.portfolio.portfolio_service import PortfolioService
from app.services.portfolio.ranking_service import RankingService
from app.services.risk.challenger_service import ChallengerService
from app.services.risk.risk_review_service import RiskReviewService
from app.services.settings_service import settings_service
from app.services.validation_service import ValidationService

router = APIRouter(tags=["health"])
market_router = APIRouter(prefix="/v1/market", tags=["market"])
governance_router = APIRouter(prefix="/v1/governance", tags=["governance"])
opportunity_router = APIRouter(prefix="/v1/opportunities", tags=["opportunities"])
risk_router = APIRouter(prefix="/v1/risk", tags=["risk"])
portfolio_router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])
execution_router = APIRouter(prefix="/v1/execution", tags=["execution"])
memory_router = APIRouter(prefix="/v1/memory", tags=["memory"])
settings_router = APIRouter(prefix="/v1/settings", tags=["settings"])

market_data_service = MarketDataService()
validation_service = ValidationService()
opportunity_repository = OpportunityRepository()
opportunity_service = OpportunityFactoryService(repository=opportunity_repository)
challenger_service = ChallengerService(repository=opportunity_repository)
risk_review_service = RiskReviewService(repository=opportunity_repository)
portfolio_service = PortfolioService()
ranking_service = RankingService()
allocation_service = AllocationService()
execution_service = PaperExecutionService(allocation_lookup=opportunity_repository.get_allocation)


def candidate_to_api(candidate: dict) -> dict:
    return {
        "candidateId": candidate["candidate_id"],
        "podName": candidate["pod_name"],
        "setupFamily": candidate["setup_family"],
        "asset": candidate["asset"],
        "direction": candidate["direction"],
        "timeframe": candidate["timeframe"],
        "entryZoneLow": float(candidate["entry_zone_low"]),
        "entryZoneHigh": float(candidate["entry_zone_high"]),
        "hardStop": float(candidate["hard_stop"]),
        "target1": float(candidate["target_1"]),
        "target2": float(candidate["target_2"]),
        "holdingHorizon": candidate["holding_horizon"],
        "thesis": candidate["thesis"],
        "invalidation": candidate["invalidation"],
        "requiresHumanReview": bool(candidate["requires_human_review"]),
        "discoveredAt": candidate["discovered_at"],
        "status": candidate["status"],
        "trustGrade": candidate["trust_grade"],
        "setupQuality": float(candidate["setup_quality"]),
        "regimeFit": float(candidate["regime_fit"]),
        "executionQualityForecast": float(candidate["execution_quality_forecast"]),
        "dataConfidence": float(candidate["data_confidence"]),
    }


def validation_to_api(validation: dict) -> dict:
    source_health = validation.get("source_health", {})
    return {
        "freshnessOk": bool(validation.get("freshness_ok")),
        "staleDetected": bool(validation.get("stale_detected")),
        "conflictDetected": bool(validation.get("conflict_detected")),
        "trustGrade": validation.get("trust_grade"),
        "sourceHealth": {
            "source": source_health.get("source"),
            "status": source_health.get("status"),
            "latencyMs": source_health.get("latency_ms"),
            "staleSeconds": source_health.get("stale_seconds"),
            "trustGrade": source_health.get("trust_grade"),
            "updatedAt": source_health.get("updated_at"),
        },
    }


def bar_to_api(bar: dict) -> dict:
    return {
        "symbol": bar.get("symbol"),
        "ts": bar.get("ts"),
        "open": bar.get("open"),
        "high": bar.get("high"),
        "low": bar.get("low"),
        "close": bar.get("close"),
        "volume": bar.get("volume"),
        "source": bar.get("source"),
        "trustGrade": bar.get("trust_grade"),
    }


def quote_to_api(quote: dict) -> dict:
    return {
        "symbol": quote.get("symbol"),
        "ts": quote.get("ts"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "last": quote.get("last"),
        "source": quote.get("source"),
        "trustGrade": quote.get("trust_grade"),
    }


class TransitionRequest(BaseModel):
    toState: Literal["GREEN", "YELLOW", "RED", "BLACKOUT"]
    reasonCode: str = Field(min_length=2)
    note: str = ""


class KillRequest(BaseModel):
    reasonCode: str = Field(min_length=2)
    note: str = ""


class OpportunityScanRequest(BaseModel):
    assets: list[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "BTCUSD"])


class CandidateActionRequest(BaseModel):
    candidateId: str = Field(min_length=3)


class RankRequest(BaseModel):
    candidateIds: list[str] = Field(default_factory=list)


class PaperOrderRequest(BaseModel):
    candidateId: str
    symbol: str
    direction: Literal["LONG", "SHORT"] = "LONG"
    podName: str = "unknown"
    qty: float = 1.0
    price: float = 100.0


class PositionManageRequest(BaseModel):
    positionId: int
    action: Literal["partial_exit", "stop", "target", "flat", "cancel"]


class JournalWriteRequest(BaseModel):
    journalType: Literal["CANDIDATE_NOTE", "POSITION_NOTE", "POST_TRADE_SUMMARY"] = "POST_TRADE_SUMMARY"
    summary: str = ""
    asset: str | None = None
    pod: str | None = None
    candidateId: str | None = None
    positionId: int | None = None
    paperOrderId: int | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryStoreRequest(BaseModel):
    memoryType: Literal["EPISODIC", "SEMANTIC", "PROCEDURAL"]
    summary: str
    asset: str | None = None
    pod: str | None = None
    regime: str | None = None
    setupFamily: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemorySearchRequest(BaseModel):
    query: str = ""
    asset: str | None = None
    pod: str | None = None
    regime: str | None = None
    setupFamily: str | None = None


class ReviewGenerateRequest(BaseModel):
    positionId: int | None = None
    candidateId: str | None = None
    asset: str | None = None
    pod: str | None = None
    processScore: float = 0.78
    executionScore: float = 0.74
    outcomeScore: float = 0.70
    reviewSummary: str = ""


class PolicyProposalRequest(BaseModel):
    proposalType: str = "PROCESS"
    title: str
    rationale: str
    proposedBy: str = "memory-service"


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "trading_mode": "paper",
        "paperTradingOnly": settings.paper_trading_only,
        "liveExecutionEnabled": settings.live_execution_enabled,
    }


@market_router.get("/bars")
def market_bars(symbol: str = "AAPL", interval: str = "1m", limit: int = 20) -> dict:
    payload = market_data_service.get_bars(symbol=symbol, interval=interval, limit=min(max(limit, 1), 200))
    validation = validation_service.assess_market_payload(payload)
    return {
        "symbol": payload.get("symbol"),
        "interval": payload.get("interval"),
        "bars": [bar_to_api(b) for b in payload.get("bars", [])],
        "source": payload.get("source"),
        "trustGrade": validation.get("trust_grade"),
        "validation": validation_to_api(validation),
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@market_router.get("/quote")
def market_quote(symbol: str = "AAPL") -> dict:
    payload = market_data_service.get_quote(symbol=symbol)
    validation = validation_service.assess_market_payload({"bars": [payload["quote"]], "source": payload["source"]})
    return {
        "symbol": payload.get("symbol"),
        "quote": quote_to_api(payload.get("quote", {})),
        "source": payload.get("source"),
        "trustGrade": validation.get("trust_grade"),
        "validation": validation_to_api(validation),
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@market_router.get("/source-health")
def market_source_health() -> dict:
    source_health = market_data_service.get_source_health()
    checks = source_health.get("checks", [])
    return {
        "checks": [
            {
                "source": check.get("source"),
                "status": check.get("status"),
                "latencyMs": check.get("latency_ms"),
                "staleSeconds": check.get("stale_seconds"),
                "trustGrade": check.get("trust_grade"),
                "updatedAt": check.get("checked_at"),
            }
            for check in checks
        ],
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@governance_router.get("/state")
def governance_state() -> dict:
    state = governance_service.get_state()
    return {
        "state": state["state"],
        "reasonCode": state["reason_code"],
        "newTradeAllowed": state["new_trade_allowed"],
        "sizeHaircut": state["size_haircut"],
        "serviceHealth": [
            {"service": h.get("service"), "status": h.get("status"), "latencyMs": h.get("latency_ms", 0)}
            for h in state["service_health"]
        ],
        "killSwitchEvents": [
            {"reasonCode": e.get("reason_code"), "note": e.get("note"), "createdAt": e.get("created_at")}
            for e in state["kill_switch_events"]
        ],
        "transitionLog": [
            {
                "fromState": e.get("from_state"),
                "toState": e.get("to_state"),
                "reasonCode": e.get("reason_code"),
                "note": e.get("note"),
                "createdAt": e.get("created_at"),
            }
            for e in state["transition_log"]
        ],
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@governance_router.post("/transition")
def governance_transition(request: TransitionRequest) -> dict:
    result = governance_service.transition(to_state=request.toState, reason_code=request.reasonCode, note=request.note)
    if not result.get("ok"):
        return result
    return governance_state()


@governance_router.post("/kill")
def governance_kill(request: KillRequest) -> dict:
    result = governance_service.trigger_kill_switch(reason_code=request.reasonCode, note=request.note)
    if not result.get("ok"):
        return result
    return governance_state()


@opportunity_router.post("/scan")
def opportunities_scan(request: OpportunityScanRequest) -> dict:
    scan = opportunity_service.scan(assets=request.assets)
    return {
        "scannedAssets": scan["scanned_assets"],
        "candidateCount": scan["candidate_count"],
        "candidates": [candidate_to_api(c) for c in scan["candidates"]],
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@opportunity_router.get("/candidates")
def opportunities_candidates() -> dict:
    candidates = [candidate_to_api(c) for c in opportunity_service.list_candidates()]
    return {"candidates": candidates, "count": len(candidates), "paperTradingOnly": True, "liveExecutionEnabled": False}


@opportunity_router.get("/candidates/{candidate_id}")
def opportunities_candidate_detail(candidate_id: str) -> dict:
    candidate = opportunity_service.get_candidate(candidate_id)
    if not candidate:
        return {"ok": False, "error": "candidate_not_found", "candidateId": candidate_id}

    challenge = opportunity_repository.get_challenge(candidate_id)
    review = opportunity_repository.get_review(candidate_id)
    return {
        "ok": True,
        "candidate": candidate_to_api(candidate),
        "challenge": {
            "candidateId": challenge["candidate_id"],
            "decision": challenge["decision"],
            "confidence": challenge["confidence"],
            "challengeSummary": challenge["challenge_summary"],
            "riskFlags": challenge["risk_flags"],
        }
        if challenge
        else None,
        "riskReview": {
            "candidateId": review["candidate_id"],
            "outcome": review["outcome"],
            "reason": review["reason"],
            "sizeAdjustment": review["size_adjustment"],
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        if review
        else None,
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@risk_router.post("/challenge")
def risk_challenge(request: CandidateActionRequest) -> dict:
    result = challenger_service.run(candidate_id=request.candidateId)
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "candidateId": result["candidate_id"],
        "decision": result["decision"],
        "confidence": result["confidence"],
        "challengeSummary": result["challenge_summary"],
        "riskFlags": result["risk_flags"],
        "status": result["status"],
    }


@risk_router.post("/review")
def risk_review(request: CandidateActionRequest) -> dict:
    result = risk_review_service.review(candidate_id=request.candidateId)
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "candidateId": result["candidate_id"],
        "outcome": result["outcome"],
        "reason": result["reason"],
        "sizeAdjustment": result["size_adjustment"],
        "paperTradingOnly": result["paper_trading_only"],
        "liveExecutionEnabled": result["live_execution_enabled"],
        "status": result["status"],
    }


@portfolio_router.post("/rank")
def portfolio_rank(request: RankRequest) -> dict:
    candidates = opportunity_service.list_candidates()
    surviving = [c for c in candidates if c.get("status") not in {"REJECTED", "HOLD"}]
    if request.candidateIds:
        surviving = [c for c in surviving if c["candidate_id"] in request.candidateIds]

    portfolio_service.set_open_positions(
        [
            {
                "symbol": p.get("symbol"),
                "pod_name": p.get("podName"),
                "direction": p.get("direction"),
                "asset_class": p.get("assetClass", "unknown"),
                "market_value": p.get("marketValue", 0),
            }
            for p in execution_service.get_open_positions()["positions"]
        ]
    )
    fit_map = portfolio_service.portfolio_fit_for_candidates(surviving)
    ranked = ranking_service.rank_batch(surviving, fit_map)
    for row in ranked:
        opportunity_repository.save_scores(row["candidate_id"], row)

    return {
        "ranked": [
            {
                "candidateId": row["candidate_id"],
                "setupQuality": float(row["setup_quality"]),
                "regimeFit": float(row["regime_fit"]),
                "dataConfidence": float(row["data_confidence"]),
                "executionQuality": float(row["execution_quality"]),
                "portfolioFit": float(row["portfolio_fit"]),
                "historicalExpectancy": float(row["historical_expectancy"]),
                "fragility": float(row["fragility"]),
                "finalScore": float(row["final_score"]),
                "rankInBatch": row["rank_in_batch"],
            }
            for row in ranked
        ],
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@portfolio_router.post("/allocate")
def portfolio_allocate(request: CandidateActionRequest) -> dict:
    candidate = opportunity_repository.get_candidate(request.candidateId)
    if not candidate:
        return {"ok": False, "error": "candidate_not_found"}

    risk_review_result = opportunity_repository.get_review(request.candidateId)
    allocation = allocation_service.allocate(candidate, risk_review_result)
    if allocation.get("ok"):
        opportunity_repository.save_allocation(request.candidateId, allocation)

    return {
        "ok": allocation["ok"],
        "candidateId": allocation.get("candidate_id"),
        "decision": allocation["decision"],
        "approvedSizeUsd": allocation.get("approved_size_usd"),
        "tradeRiskPct": allocation.get("trade_risk_pct"),
        "sizingMultiplier": allocation.get("sizing_multiplier"),
        "reason": allocation.get("reason"),
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@portfolio_router.get("/exposure")
def portfolio_exposure() -> dict:
    portfolio_service.set_open_positions(
        [
            {
                "symbol": p.get("symbol"),
                "pod_name": p.get("podName"),
                "direction": p.get("direction"),
                "asset_class": p.get("assetClass", "unknown"),
                "market_value": p.get("marketValue", 0),
            }
            for p in execution_service.get_open_positions()["positions"]
        ]
    )
    exposure = portfolio_service.exposure_summary()
    return {
        "byAsset": exposure["by_asset"],
        "bySleeve": exposure["by_sleeve"],
        "byDirection": exposure["by_direction"],
        "byAssetClass": exposure["by_asset_class"],
        "paperTradingOnly": True,
        "liveExecutionEnabled": False,
    }


@execution_router.post("/orders/paper")
def execution_paper_order(request: PaperOrderRequest) -> dict:
    return execution_service.place_paper_order(request.model_dump())


@execution_router.get("/positions/open")
def execution_open_positions() -> dict:
    return execution_service.get_open_positions()


@execution_router.post("/positions/manage")
def execution_manage_position(request: PositionManageRequest) -> dict:
    result = execution_service.manage_position(position_id=request.positionId, action=request.action)
    result["events"] = execution_service.event_log()
    return result


@memory_router.post("/journal")
def memory_journal_write(request: JournalWriteRequest) -> dict:
    return memory_service.write_journal(request.model_dump())


@memory_router.post("/store")
def memory_store(request: MemoryStoreRequest) -> dict:
    return memory_service.store_memory(request.model_dump())


@memory_router.post("/search")
def memory_search(request: MemorySearchRequest) -> dict:
    return memory_service.search_memory(request.model_dump())


@memory_router.post("/reviews/generate")
def memory_generate_review(request: ReviewGenerateRequest) -> dict:
    return memory_service.generate_review(request.model_dump())


@memory_router.get("/review/{positionId}")
def memory_review_by_position(positionId: int) -> dict:
    return memory_service.get_review_by_position(position_id=positionId)


@memory_router.get("/reviews")
def memory_reviews(candidateId: str | None = None) -> dict:
    return memory_service.list_reviews(candidate_id=candidateId)


@memory_router.get("/pod-performance")
def memory_pod_performance() -> dict:
    return memory_service.aggregate_pod_performance()


@memory_router.post("/policy-queue")
def memory_policy_queue_write(request: PolicyProposalRequest) -> dict:
    return memory_service.create_policy_proposal(request.model_dump())


@memory_router.get("/policy-queue")
def memory_policy_queue_read() -> dict:
    return memory_service.list_policy_queue()


@settings_router.get("/visibility")
def settings_visibility() -> dict:
    return settings_service.get_visibility()
