from __future__ import annotations

from decimal import Decimal

from app.services.governance_service import governance_service
from app.services.risk.risk_engine import risk_engine


class AllocationService:
    """Sizes an approved candidate through the real risk engine, AFTER the
    governance kill switch. Governance and risk both OVERRIDE the strategy: either
    can reject or shrink, neither can enlarge."""

    def __init__(self, governance=governance_service, engine=risk_engine) -> None:
        self.governance = governance
        self.engine = engine

    def allocate(self, candidate: dict, risk_review: dict | None) -> dict:
        base = {"paper_trading_only": True, "live_execution_enabled": False}

        # 1 · GOVERNANCE KILL SWITCH — no allocation in RED/BLACKOUT (audit C1).
        gov = self.governance.get_state()
        if not gov.get("new_trade_allowed", False):
            return {"ok": False, "decision": "REJECT",
                    "reason": f"governance_blocked:{gov.get('state')}", **base}
        size_haircut = Decimal(str(gov.get("size_haircut", 0)))

        # 2 · risk review must have approved/reduced
        if not risk_review or risk_review.get("outcome") not in {"APPROVE", "REDUCE"}:
            return {"ok": False, "decision": "REJECT",
                    "reason": "risk_review_not_approved", **base}

        # 3 · entry + hard stop are REQUIRED to size on real risk-per-trade
        entry = candidate.get("entry_zone_low", candidate.get("entry"))
        stop = candidate.get("hard_stop")
        if entry in (None, "") or stop in (None, ""):
            return {"ok": False, "decision": "REJECT", "reason": "entry_or_stop_missing", **base}
        entry_d, stop_d = Decimal(str(entry)), Decimal(str(stop))

        # 4 · quality multiplier (bounded), then risk-review + governance haircuts
        quality = Decimal(str(candidate.get("setup_quality", 0.5)))
        regime = Decimal(str(candidate.get("regime_fit", 0.5)))
        trust = Decimal(str(candidate.get("data_confidence", 0.5)))
        quality_mult = ((Decimal("0.8") + quality * Decimal("0.4"))
                        * (Decimal("0.8") + regime * Decimal("0.3"))
                        * (Decimal("0.8") + trust * Decimal("0.3")))
        review_adj = Decimal(str(risk_review.get("size_adjustment", 1)))
        quality_mult = min(quality_mult * review_adj, Decimal("1.4"))

        # 5 · REAL EQUITY-BASED SIZING + portfolio limits (audit C4). The engine is
        #     the final gate — daily-loss, drawdown, exposure and per-trade caps.
        sized = self.engine.size_and_check(
            candidate.get("symbol", candidate.get("asset", "UNKNOWN")),
            entry_d, stop_d, size_haircut=size_haircut, quality_mult=quality_mult,
        )
        if not sized.get("ok"):
            return {"ok": False, "decision": "REJECT", "reason": f"risk_engine:{sized['reason']}", **base}

        return {
            "ok": True,
            "candidate_id": candidate["candidate_id"],
            "symbol": sized["symbol"],
            "decision": "ALLOCATE",
            "approved_size_usd": sized["market_value_usd"],
            "approved_qty": sized["qty"],
            "risk_amount_usd": sized["risk_amount_usd"],
            "trade_risk_pct": sized["risk_pct_of_equity"],
            "sizing_multiplier": float(quality_mult.quantize(Decimal("0.0001"))),
            "governance_state": gov.get("state"),
            "size_haircut": float(size_haircut),
            "verdict": sized["verdict"],
            **base,
        }
