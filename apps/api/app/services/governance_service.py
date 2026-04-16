from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

CompanyState = Literal["GREEN", "YELLOW", "RED", "BLACKOUT"]


@dataclass
class TransitionEvent:
    from_state: CompanyState
    to_state: CompanyState
    reason_code: str
    note: str
    created_at: str


@dataclass
class KillSwitchEvent:
    reason_code: str
    note: str
    created_at: str


@dataclass
class GovernanceSnapshot:
    state: CompanyState = "GREEN"
    reason_code: str = "INIT"
    new_trade_allowed: bool = True
    size_haircut: float = 0.0
    transition_log: list[TransitionEvent] = field(default_factory=list)
    kill_switch_events: list[KillSwitchEvent] = field(default_factory=list)
    service_health: list[dict] = field(default_factory=list)


class GovernanceService:
    def __init__(self) -> None:
        self.snapshot = GovernanceSnapshot(
            service_health=[
                {"service": "market-data", "status": "ok", "latency_ms": 95},
                {"service": "validation", "status": "ok", "latency_ms": 40},
                {"service": "governance", "status": "ok", "latency_ms": 25},
            ]
        )

    def _apply_state_effects(self, state: CompanyState) -> tuple[bool, float]:
        if state == "GREEN":
            return True, 0.0
        if state == "YELLOW":
            return True, 0.35
        if state == "RED":
            return False, 1.0
        return False, 1.0

    def get_state(self) -> dict:
        return {
            "state": self.snapshot.state,
            "reason_code": self.snapshot.reason_code,
            "new_trade_allowed": self.snapshot.new_trade_allowed,
            "size_haircut": self.snapshot.size_haircut,
            "service_health": self.snapshot.service_health,
            "kill_switch_events": [event.__dict__ for event in self.snapshot.kill_switch_events],
            "transition_log": [event.__dict__ for event in self.snapshot.transition_log],
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def transition(self, to_state: CompanyState, reason_code: str, note: str = "") -> dict:
        now = datetime.now(tz=timezone.utc).isoformat()
        from_state = self.snapshot.state

        allowed = {
            "GREEN": {"YELLOW", "RED", "BLACKOUT"},
            "YELLOW": {"GREEN", "RED", "BLACKOUT"},
            "RED": {"YELLOW", "BLACKOUT"},
            "BLACKOUT": {"YELLOW"},
        }
        if to_state not in allowed[from_state]:
            return {
                "ok": False,
                "error": f"invalid transition {from_state} -> {to_state}",
                "state": from_state,
            }

        self.snapshot.state = to_state
        self.snapshot.reason_code = reason_code
        self.snapshot.new_trade_allowed, self.snapshot.size_haircut = self._apply_state_effects(to_state)
        self.snapshot.transition_log.insert(
            0,
            TransitionEvent(
                from_state=from_state,
                to_state=to_state,
                reason_code=reason_code,
                note=note,
                created_at=now,
            ),
        )
        return {"ok": True, **self.get_state()}

    def trigger_kill_switch(self, reason_code: str, note: str = "") -> dict:
        now = datetime.now(tz=timezone.utc).isoformat()
        self.snapshot.kill_switch_events.insert(0, KillSwitchEvent(reason_code=reason_code, note=note, created_at=now))
        return self.transition(to_state="BLACKOUT", reason_code=reason_code, note=note)


governance_service = GovernanceService()
