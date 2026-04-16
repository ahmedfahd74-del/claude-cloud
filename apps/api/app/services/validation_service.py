from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ValidationService:
    def assess_market_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        bars = payload.get("bars", [])

        freshness_ok = True
        stale = False
        conflict = False
        if bars:
            latest_ts = bars[-1].get("ts")
            try:
                latest = datetime.fromisoformat(str(latest_ts))
                age_seconds = int((now - latest).total_seconds())
                freshness_ok = age_seconds < 180
                stale = age_seconds >= 180
            except ValueError:
                freshness_ok = False
                stale = True
                age_seconds = -1
        else:
            age_seconds = -1
            freshness_ok = False
            stale = True

        trust = "A" if freshness_ok else "C"
        if conflict:
            trust = "D"

        source_health = {
            "source": payload.get("source", "unknown"),
            "status": "ok" if freshness_ok else "degraded",
            "latency_ms": 120,
            "stale_seconds": max(age_seconds, 0),
            "trust_grade": trust,
            "updated_at": now.isoformat(),
        }

        return {
            "freshness_ok": freshness_ok,
            "stale_detected": stale,
            "conflict_detected": conflict,
            "trust_grade": trust,
            "source_health": source_health,
        }
