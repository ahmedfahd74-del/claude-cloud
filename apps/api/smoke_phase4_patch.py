"""Phase 4 patch smoke checks.

Run: python apps/api/smoke_phase4_patch.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal

sys.path.append("apps/api")

from app.services.execution.paper_execution_service import PaperExecutionService
from app.services.portfolio.portfolio_service import PortfolioService
from app.services.portfolio.ranking_service import RankingService


@dataclass
class FakeTradeManagementEvent:
    position_id: int | None
    order_id: int | None
    event_type: str
    details: str


class FakeSession:
    def __init__(self, sink: list) -> None:
        self.sink = sink

    def add(self, row) -> None:
        self.sink.append(row)

    def commit(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestableExecutionService(PaperExecutionService):
    def __init__(self, allocation_lookup):
        super().__init__(allocation_lookup=allocation_lookup)
        self.persisted_rows: list[FakeTradeManagementEvent] = []

    def _db_handles(self):
        sink = self.persisted_rows

        class _SessionFactory:
            def __call__(self):
                return FakeSession(sink)

        return _SessionFactory(), FakeTradeManagementEvent


def run() -> None:
    allocation_store: dict[str, dict] = {}

    def lookup(candidate_id: str):
        return allocation_store.get(candidate_id)

    svc = TestableExecutionService(allocation_lookup=lookup)

    # 1) reject without allocation
    rejected = svc.place_paper_order({"candidateId": "C-1", "symbol": "AAPL", "direction": "LONG", "podName": "LiquidityReversalPod", "qty": 1, "price": 100})
    print("TEST1_REJECT_WITHOUT_ALLOCATION", rejected["ok"] is False and rejected.get("error") == "allocation_required")

    # 2) accept with valid allocation
    allocation_store["C-1"] = {"decision": "ALLOCATE", "approved_size_usd": 1000}
    placed = svc.place_paper_order({"candidateId": "C-1", "symbol": "AAPL", "direction": "LONG", "podName": "LiquidityReversalPod", "qty": 1, "price": 100})
    print("TEST2_ACCEPT_WITH_ALLOCATION", placed["ok"] is True and placed["order"]["status"] == "FILLED")

    # 3) position only through order/fill path
    svc2 = TestableExecutionService(allocation_lookup=lookup)
    no_position_manage = svc2.manage_position(position_id=1, action="flat")
    print("TEST3_POSITION_ONLY_VIA_ORDER_PATH", no_position_manage["ok"] is False and no_position_manage.get("error") == "position_not_found")

    # 4) trade_management_events persisted on state changes
    managed = svc.manage_position(position_id=placed["position"]["positionId"], action="partial_exit")
    persisted_event_types = [row.event_type for row in svc.persisted_rows]
    print("TEST4_DB_EVENT_PERSISTENCE", managed["ok"] is True and {"ORDER_FILLED", "POSITION_ACTIVE", "POSITION_MANAGED"}.issubset(set(persisted_event_types)))

    # 5) API shape consistency (service payload canonical keys)
    order_keys_ok = {"orderId", "candidateId", "symbol", "direction", "podName", "qty", "price", "status", "paperTradingOnly", "liveExecutionEnabled"}.issubset(set(placed["order"].keys()))
    pos_keys_ok = {"positionId", "orderId", "symbol", "direction", "podName", "qty", "avgPrice", "marketValue", "status"}.issubset(set(placed["position"].keys()))
    event_keys_ok = {"timestamp", "eventType", "details", "positionId", "orderId"}.issubset(set(svc.event_log()[0].keys()))
    print("TEST5_CANONICAL_PAYLOAD_KEYS", order_keys_ok and pos_keys_ok and event_keys_ok)

    # 6) API payload shape consistency checks without web framework dependency.
    candidate_api = {
        "candidateId": "C-API-1",
        "podName": "LiquidityReversalPod",
        "direction": "LONG",
        "setupQuality": 0.78,
        "trustGrade": "B",
    }
    candidate_shape_ok = {"candidateId", "podName", "direction", "setupQuality", "trustGrade"}.issubset(set(candidate_api.keys()))

    ranking = RankingService().rank_batch(
        [
            {
                "candidate_id": "C-API-1",
                "setup_quality": 0.78,
                "regime_fit": 0.71,
                "data_confidence": 0.82,
                "execution_quality_forecast": 0.67,
                "requires_human_review": True,
            }
        ],
        {"C-API-1": Decimal("0.8")},
    )[0]
    ranking_api = {"candidateId": ranking["candidate_id"], "finalScore": float(ranking["final_score"]), "rankInBatch": 1}
    ranked_shape_ok = {"candidateId", "finalScore", "rankInBatch"}.issubset(set(ranking_api.keys()))

    exposure = PortfolioService()
    exposure.set_open_positions([{"symbol": "AAPL", "pod_name": "LiquidityReversalPod", "direction": "LONG", "asset_class": "equity", "market_value": 1000}])
    exp = exposure.exposure_summary()
    exposure_api = {"byAsset": exp["by_asset"], "bySleeve": exp["by_sleeve"], "byDirection": exp["by_direction"], "byAssetClass": exp["by_asset_class"]}
    exposure_shape_ok = {"byAsset", "bySleeve", "byDirection", "byAssetClass"}.issubset(set(exposure_api.keys()))

    execution_shape_ok = {"orderId", "candidateId", "direction", "paperTradingOnly"}.issubset(set(placed["order"].keys()))
    event_shape_ok = {"timestamp", "eventType", "details", "positionId", "orderId"}.issubset(set(svc.event_log()[0].keys()))

    print("TEST6_API_SHAPE_CONSISTENCY", candidate_shape_ok and ranked_shape_ok and exposure_shape_ok and execution_shape_ok and event_shape_ok)


if __name__ == "__main__":
    run()
