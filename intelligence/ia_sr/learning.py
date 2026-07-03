"""Learning Engine — outcome store + performance-based calibration.

SQLite (stdlib) store of every emitted signal and its resolved outcome. The
lifecycle simulation mirrors the Pine Section 14B journal: limit fill within
FILL_WIN base bars, conservative stop-first stop/TP1 race, LIFE-bar timeout
resolved by sign of open PnL. Calibration buckets (<70 / 70-80 / 80+) compare
predicted probability with realised win rate; `calibrate()` shrinks new
predictions toward the realised rate once a bucket has enough samples.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

from .indicators import Bar

FILL_WIN = 40
LIFE = 200
MIN_SAMPLES = 20      # bucket size before calibration kicks in
SHRINK = 0.5          # weight given to realised rate once calibrated

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts INTEGER NOT NULL,
    bar_ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    direction TEXT NOT NULL,
    prob REAL NOT NULL,
    quality TEXT NOT NULL,
    state TEXT NOT NULL,
    entry REAL, stop REAL, tp1 REAL,
    evidence TEXT,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending|filled|win|loss|cancelled
    fill_ts INTEGER,
    resolved_ts INTEGER,
    outcome_r REAL
);
CREATE TABLE IF NOT EXISTS pine_payloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_ts INTEGER NOT NULL,
    payload TEXT NOT NULL
);
"""


@dataclass
class BucketStats:
    label: str
    n: int
    expected: float    # mean predicted probability
    actual: float      # realised win rate (%)

    @property
    def gap(self) -> float:
        return self.expected - self.actual


class LearningEngine:
    def __init__(self, db_path: str = "ia_sr.db"):
        self.db = sqlite3.connect(db_path)
        self.db.executescript(_SCHEMA)

    # -- recording -----------------------------------------------------------
    def record(self, analysis, tf: str) -> int | None:
        """Store a validated plan as a pending signal (idempotent per bar)."""
        plan = analysis.plan
        if not plan.valid:
            return None
        dup = self.db.execute(
            "SELECT id FROM signals WHERE symbol=? AND tf=? AND bar_ts=?",
            (analysis.symbol, tf, analysis.ts)).fetchone()
        if dup:
            return dup[0]
        cur = self.db.execute(
            "INSERT INTO signals (created_ts, bar_ts, symbol, tf, direction, prob,"
            " quality, state, entry, stop, tp1, evidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(time.time()), analysis.ts, analysis.symbol, tf, plan.direction,
             analysis.probability.dir_prob, analysis.probability.quality,
             analysis.decision.market_state, plan.entry, plan.stop, plan.tp1,
             analysis.probability.evidence_text()))
        self.db.commit()
        return cur.lastrowid

    def record_pine_payload(self, payload: dict) -> None:
        self.db.execute("INSERT INTO pine_payloads (received_ts, payload) VALUES (?,?)",
                        (int(time.time()), json.dumps(payload)))
        self.db.commit()

    # -- resolution (Pine Section 14B lifecycle) ------------------------------
    def resolve_open(self, feed, base_tf: str, tf_minutes: float) -> int:
        """Walk unresolved signals against fresh bars; returns #resolved."""
        rows = self.db.execute(
            "SELECT id, bar_ts, symbol, direction, entry, stop, tp1, status, fill_ts"
            " FROM signals WHERE status IN ('pending','filled')").fetchall()
        resolved = 0
        step = int(tf_minutes * 60)
        for sid, bar_ts, symbol, direction, entry, stop, tp1, status, fill_ts in rows:
            bars = [b for b in feed.bars(symbol, base_tf, 2000) if b.ts > bar_ts]
            d = 1 if direction == "LONG" else -1
            filled_at = fill_ts
            outcome = None
            r = None
            for b in bars:
                if filled_at is None:
                    if (d == 1 and b.low <= entry) or (d == -1 and b.high >= entry):
                        filled_at = b.ts
                    elif b.ts - bar_ts > FILL_WIN * step:
                        outcome = ("cancelled", None)
                        break
                if filled_at is not None:
                    if (d == 1 and b.low <= stop) or (d == -1 and b.high >= stop):
                        outcome = ("loss", -1.0)
                        break
                    if (d == 1 and b.high >= tp1) or (d == -1 and b.low <= tp1):
                        risk = abs(entry - stop)
                        outcome = ("win", abs(tp1 - entry) / risk if risk else 0.0)
                        break
                    if b.ts - filled_at > LIFE * step:
                        risk = abs(entry - stop)
                        pnl_r = (b.close - entry) * d / risk if risk else 0.0
                        outcome = ("win" if pnl_r > 0 else "loss", pnl_r)
                        break
            if outcome:
                self.db.execute(
                    "UPDATE signals SET status=?, outcome_r=?, resolved_ts=?, fill_ts=? WHERE id=?",
                    (outcome[0], outcome[1], int(time.time()), filled_at, sid))
                resolved += 1
            elif filled_at is not None and status == "pending":
                self.db.execute("UPDATE signals SET status='filled', fill_ts=? WHERE id=?",
                                (filled_at, sid))
        self.db.commit()
        return resolved

    # -- calibration -----------------------------------------------------------
    def buckets(self) -> list[BucketStats]:
        out = []
        for label, lo, hi in (("<70", 0, 70), ("70-80", 70, 80), ("80+", 80, 101)):
            rows = self.db.execute(
                "SELECT prob, status FROM signals WHERE status IN ('win','loss')"
                " AND prob >= ? AND prob < ?", (lo, hi)).fetchall()
            n = len(rows)
            if n:
                exp = sum(p for p, _ in rows) / n
                act = 100.0 * sum(1 for _, s in rows if s == "win") / n
            else:
                exp = act = 0.0
            out.append(BucketStats(label, n, exp, act))
        return out

    def calibrate(self, prob: float) -> float:
        """Shrink a predicted probability toward the realised rate of its bucket."""
        for b, lo, hi in zip(self.buckets(), (0, 70, 80), (70, 80, 101)):
            if lo <= prob < hi and b.n >= MIN_SAMPLES:
                return (1 - SHRINK) * prob + SHRINK * b.actual
        return prob
