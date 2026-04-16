from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


class PortfolioService:
    def __init__(self) -> None:
        self._open_positions: list[dict] = []

    def set_open_positions(self, positions: list[dict]) -> None:
        self._open_positions = positions

    def exposure_summary(self) -> dict:
        by_asset: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_sleeve: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_direction: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_asset_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for pos in self._open_positions:
            value = Decimal(str(pos.get("market_value", 0)))
            by_asset[pos.get("symbol", "UNKNOWN")] += value
            by_sleeve[pos.get("pod_name", "unknown")] += value
            by_direction[pos.get("direction", "UNKNOWN")] += value
            by_asset_class[pos.get("asset_class", "unknown")] += value

        return {
            "by_asset": {k: float(v) for k, v in by_asset.items()},
            "by_sleeve": {k: float(v) for k, v in by_sleeve.items()},
            "by_direction": {k: float(v) for k, v in by_direction.items()},
            "by_asset_class": {k: float(v) for k, v in by_asset_class.items()},
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def portfolio_fit_for_candidates(self, candidates: list[dict]) -> dict[str, Decimal]:
        asset_counts = defaultdict(int)
        direction_counts = defaultdict(int)
        sleeve_counts = defaultdict(int)
        for pos in self._open_positions:
            asset_counts[pos.get("symbol", "UNKNOWN")] += 1
            direction_counts[pos.get("direction", "UNKNOWN")] += 1
            sleeve_counts[pos.get("pod_name", "unknown")] += 1

        fit_map: dict[str, Decimal] = {}
        for c in candidates:
            score = Decimal("1.00")
            if asset_counts[c["asset"]] > 0:
                score -= Decimal("0.25")
            if direction_counts[c["direction"]] > 1:
                score -= Decimal("0.20")
            if sleeve_counts[c["pod_name"]] > 0:
                score -= Decimal("0.20")
            fit_map[c["candidate_id"]] = max(score, Decimal("0.10"))
        return fit_map
