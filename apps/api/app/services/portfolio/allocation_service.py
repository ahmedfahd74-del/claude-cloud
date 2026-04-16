from __future__ import annotations

from decimal import Decimal


class AllocationService:
    def __init__(self) -> None:
        self.base_risk = Decimal("0.005")

    def allocate(self, candidate: dict, risk_review: dict | None) -> dict:
        if not risk_review or risk_review.get("outcome") not in {"APPROVE", "REDUCE"}:
            return {
                "ok": False,
                "decision": "REJECT",
                "reason": "risk_review_not_approved",
                "paper_trading_only": True,
                "live_execution_enabled": False,
            }

        quality = Decimal(str(candidate.get("setup_quality", 0.5)))
        regime = Decimal(str(candidate.get("regime_fit", 0.5)))
        trust = Decimal(str(candidate.get("data_confidence", 0.5)))
        drawdown = Decimal("0.90")
        concentration = Decimal("0.85")

        quality_mult = Decimal("0.8") + (quality * Decimal("0.4"))
        regime_mult = Decimal("0.8") + (regime * Decimal("0.3"))
        data_mult = Decimal("0.8") + (trust * Decimal("0.3"))
        trade_risk_pct = self.base_risk * quality_mult * regime_mult * data_mult * drawdown * concentration
        size_adjustment = Decimal(str(risk_review.get("size_adjustment", 1)))
        sizing_multiplier = (quality_mult * regime_mult * data_mult * size_adjustment).quantize(Decimal("0.0001"))

        approved_size_usd = (Decimal("100000") * trade_risk_pct * size_adjustment * Decimal("10")).quantize(Decimal("0.01"))

        return {
            "ok": True,
            "candidate_id": candidate["candidate_id"],
            "decision": "ALLOCATE",
            "approved_size_usd": float(approved_size_usd),
            "trade_risk_pct": float(trade_risk_pct.quantize(Decimal("0.0001"))),
            "sizing_multiplier": float(sizing_multiplier),
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }
