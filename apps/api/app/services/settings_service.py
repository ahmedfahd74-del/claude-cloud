from __future__ import annotations

from app.core.config import settings


class SettingsService:
    def __init__(self) -> None:
        self.pod_registry = [
            {"pod": "LiquidityReversalPod", "status": "ACTIVE", "trustGrade": "B", "models": ["lrp-v1"]},
            {"pod": "ContinuationPullbackPod", "status": "ACTIVE", "trustGrade": "B", "models": ["cpp-v1"]},
        ]

    def get_visibility(self) -> dict:
        return {
            "companyPolicyDefaults": {
                "paperTradingOnly": settings.paper_trading_only,
                "liveExecutionEnabled": settings.live_execution_enabled,
                "defaultState": "GREEN",
                "defaultSizeHaircut": 0.0,
            },
            "riskDefaults": {
                "baseRiskPct": 0.005,
                "maxSingleTradeRiskPct": 0.01,
                "allocationDecisionRequired": True,
            },
            "dataRouting": {
                "sourceOrder": ["research_primary", "fallback_source", "cache_source", "crypto_exchange_native"],
                "conflictPolicy": "prefer_primary_then_fallback",
            },
            "modelRouting": {
                "rankingModel": "ranking_v1_weighted",
                "riskReviewModel": "risk_review_rules_v1",
                "executionModel": "paper_execution_sim_v1",
            },
            "pods": self.pod_registry,
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }


settings_service = SettingsService()
