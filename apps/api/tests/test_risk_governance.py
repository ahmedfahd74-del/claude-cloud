"""Unit tests for the risk engine + governance kill-switch enforcement.

Pure-logic tests — no DB, no FastAPI, run with `python3 tests/test_risk_governance.py`
from apps/api. They prove the capital-critical guarantees from the audit (C1, C3, C4):
governance can block/haircut, and the risk engine enforces daily-loss, drawdown,
per-trade risk, and exposure caps, overriding strategy signals.
"""
import sys
from decimal import Decimal

sys.path.insert(0, ".")

from app.services.risk.risk_engine import RiskEngine, RiskConfig  # noqa: E402
from app.services.portfolio.allocation_service import AllocationService  # noqa: E402
from app.services.governance_service import GovernanceService  # noqa: E402

results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond), detail))

CAND = {
    "candidate_id": "c1", "symbol": "BTCUSDT", "asset": "BTCUSDT",
    "entry_zone_low": 100.0, "hard_stop": 98.0,
    "setup_quality": 0.8, "regime_fit": 0.7, "data_confidence": 0.8,
}
APPROVED = {"outcome": "APPROVE", "size_adjustment": 1}


def fresh_alloc(gov_state=None, engine=None):
    g = GovernanceService()
    if gov_state:
        g.transition(gov_state, "TEST")
    return AllocationService(governance=g, engine=engine or RiskEngine()), g

# 1 · equity-based sizing: risk $ == equity * 1% * mult, qty = risk/stop_distance
eng = RiskEngine()
a, _ = fresh_alloc(engine=eng)
r = a.allocate(CAND, APPROVED)
ok("allocation approved on GREEN", r["ok"] and r["decision"] == "ALLOCATE", r.get("reason", ""))
# risk budget 100000*1% = 1000; quality_mult capped ≤1.4 → risk ≤ 1400, and ≤ budget=1000
ok("risk per trade never exceeds 1% cap ($1000)", r["risk_amount_usd"] <= 1000.0 + 1e-6, r["risk_amount_usd"])
# stop distance = 2 → qty = risk/2
ok("qty = risk / stop_distance", abs(r["approved_qty"] - r["risk_amount_usd"] / 2.0) < 1e-6)

# 2 · GOVERNANCE KILL SWITCH — RED blocks allocation entirely
a, _ = fresh_alloc("YELLOW")           # GREEN->YELLOW allowed
a2, g2 = fresh_alloc()
g2.transition("RED", "TEST")           # GREEN->RED allowed
a2.governance = g2
rr = a2.allocate(CAND, APPROVED)
ok("RED state blocks allocation", (not rr["ok"]) and "governance_blocked:RED" in rr["reason"], rr["reason"])

# 3 · BLACKOUT (kill switch) blocks
a3, g3 = fresh_alloc()
g3.trigger_kill_switch("PANIC")
a3.governance = g3
rb = a3.allocate(CAND, APPROVED)
ok("kill switch (BLACKOUT) blocks allocation", not rb["ok"] and "BLACKOUT" in rb["reason"], rb["reason"])

# 4 · YELLOW haircut reduces size (35% haircut) — isolate from the exposure cap by
#     lifting it so the haircut is the binding constraint
cfg_noexp = RiskConfig(max_symbol_exposure_pct=Decimal("1.0"), max_total_exposure_pct=Decimal("5.0"))
g4 = GovernanceService(); g4.transition("YELLOW", "TEST")
ry = AllocationService(governance=g4, engine=RiskEngine(cfg_noexp)).allocate(CAND, APPROVED)
rg = AllocationService(governance=GovernanceService(), engine=RiskEngine(cfg_noexp)).allocate(CAND, APPROVED)
ok("YELLOW haircut shrinks risk vs GREEN", ry["ok"] and ry["risk_amount_usd"] < rg["risk_amount_usd"], (ry["risk_amount_usd"], rg["risk_amount_usd"]))

# 5 · daily loss limit halts new trades
eng5 = RiskEngine(RiskConfig(max_daily_loss_pct=Decimal("0.03")))
eng5.start_new_day()
eng5.mark_to_market(Decimal("96000"))   # -4% on the day
a5 = AllocationService(governance=GovernanceService(), engine=eng5)
r5 = a5.allocate(CAND, APPROVED)
ok("daily loss limit halts allocation", not r5["ok"] and "daily_loss_limit_reached" in r5["reason"], r5["reason"])

# 6 · drawdown limit halts — isolate from daily-loss by starting a fresh day at the
#     drawn-down equity (small daily loss, large peak-to-trough)
eng6 = RiskEngine(RiskConfig(max_drawdown_pct=Decimal("0.10")))
eng6.mark_to_market(Decimal("120000"))  # HWM 120k
eng6.mark_to_market(Decimal("105000"))  # drift down over prior days (-12.5% from peak)
eng6.start_new_day()                    # new session opens at 105k → daily loss 0
a6 = AllocationService(governance=GovernanceService(), engine=eng6)
r6 = a6.allocate(CAND, APPROVED)
ok("max drawdown halts allocation", not r6["ok"] and "max_drawdown_reached" in r6["reason"], r6["reason"])

# 7 · per-symbol exposure cap caps market value at 20% of equity
eng7 = RiskEngine(RiskConfig(max_symbol_exposure_pct=Decimal("0.20"), max_risk_per_trade_pct=Decimal("0.05")))
a7 = AllocationService(governance=GovernanceService(), engine=eng7)
r7 = a7.allocate(CAND, APPROVED)
ok("per-symbol exposure ≤ 20% of equity", r7["ok"] and r7["approved_size_usd"] <= 20000.0 + 1e-3, r7["approved_size_usd"])

# 8 · missing hard stop → reject (no naked sizing)
a8, _ = fresh_alloc()
r8 = a8.allocate({**CAND, "hard_stop": None}, APPROVED)
ok("missing hard stop rejected", not r8["ok"] and "entry_or_stop_missing" in r8["reason"], r8["reason"])

# 9 · unapproved review → reject
a9, _ = fresh_alloc()
r9 = a9.allocate(CAND, {"outcome": "REJECT"})
ok("unapproved risk review rejected", not r9["ok"], r9["reason"])

# 10 · max open positions halts
eng10 = RiskEngine(RiskConfig(max_open_positions=2))
eng10.register_fill("X", Decimal("10")); eng10.register_fill("Y", Decimal("10"))
a10 = AllocationService(governance=GovernanceService(), engine=eng10)
r10 = a10.allocate(CAND, APPROVED)
ok("max open positions halts", not r10["ok"] and "max_open_positions_reached" in r10["reason"], r10["reason"])

print("RISK ENGINE + GOVERNANCE — UNIT TESTS")
print("=" * 60)
allok = True
for name, passed, detail in results:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f"  — {detail}" if not passed else ""))
    allok &= passed
print("=" * 60)
print("RESULT:", "ALL PASS" if allok else "FAILURES")
sys.exit(0 if allok else 1)
