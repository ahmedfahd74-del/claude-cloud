from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable


class PaperExecutionService:
    def __init__(self, allocation_lookup: Callable[[str], dict | None] | None = None) -> None:
        self.orders: list[dict] = []
        self.positions: list[dict] = []
        self.events: list[dict] = []
        self._order_seq = 1
        self._position_seq = 1
        self._allocation_lookup = allocation_lookup or (lambda _candidate_id: None)

    def place_paper_order(self, payload: dict) -> dict:
        candidate_id = payload.get("candidateId")
        allocation = self._allocation_lookup(candidate_id)
        if not allocation:
            return {
                "ok": False,
                "error": "allocation_required",
                "paperTradingOnly": True,
                "liveExecutionEnabled": False,
            }

        if allocation.get("decision") != "ALLOCATE" or float(allocation.get("approved_size_usd", allocation.get("approvedSizeUsd", 0))) <= 0:
            return {
                "ok": False,
                "error": "allocation_not_approved",
                "paperTradingOnly": True,
                "liveExecutionEnabled": False,
            }

        order = {
            "orderId": self._order_seq,
            "candidateId": candidate_id,
            "symbol": payload["symbol"],
            "direction": payload.get("direction", "LONG"),
            "podName": payload.get("podName", "unknown"),
            "qty": payload.get("qty", 1),
            "price": payload.get("price", 0),
            "status": "PENDING_ENTRY",
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        self._order_seq += 1
        self.orders.append(order)

        filled = {**order, "status": "FILLED"}
        self._log_event(orderId=order["orderId"], eventType="ORDER_FILLED", details="Paper fill simulated immediately")

        position = {
            "positionId": self._position_seq,
            "orderId": order["orderId"],
            "symbol": order["symbol"],
            "direction": order["direction"],
            "podName": order["podName"],
            "qty": order["qty"],
            "avgPrice": order["price"],
            "marketValue": order["qty"] * order["price"],
            "status": "ACTIVE",
        }
        self._position_seq += 1
        self.positions.append(position)
        self._log_event(positionId=position["positionId"], eventType="POSITION_ACTIVE", details="Position opened from paper fill")

        return {"ok": True, "order": filled, "position": position, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def get_open_positions(self) -> dict:
        open_states = {"ACTIVE", "PARTIAL_EXIT_TAKEN", "PARTIALLY_FILLED", "FILLED", "PENDING_ENTRY"}
        return {
            "positions": [p for p in self.positions if p["status"] in open_states],
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }

    def manage_position(self, position_id: int, action: str) -> dict:
        found = next((p for p in self.positions if p["positionId"] == position_id), None)
        if not found:
            return {"ok": False, "error": "position_not_found"}

        mapping = {
            "partial_exit": "PARTIAL_EXIT_TAKEN",
            "stop": "STOPPED",
            "target": "TARGET_HIT",
            "flat": "FLAT",
            "cancel": "CANCELLED",
        }
        new_status = mapping.get(action, found["status"])
        found["status"] = new_status
        self._log_event(positionId=position_id, eventType="POSITION_MANAGED", details=f"Action={action} status={new_status}")
        return {"ok": True, "position": found, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def _db_handles(self):
        try:
            from app.db.models import TradeManagementEvent
            from app.db.session import SessionLocal

            return SessionLocal, TradeManagementEvent
        except Exception:
            return None, None

    def _log_event(self, eventType: str, details: str, positionId: int | None = None, orderId: int | None = None) -> None:
        event = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "eventType": eventType,
            "details": details,
            "positionId": positionId,
            "orderId": orderId,
        }
        self.events.insert(0, event)

        SessionLocal, TradeManagementEvent = self._db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                session.add(
                    TradeManagementEvent(
                        position_id=positionId,
                        order_id=orderId,
                        event_type=eventType,
                        details=details,
                    )
                )
                session.commit()
        except Exception:
            pass

    def event_log(self) -> list[dict]:
        return self.events
