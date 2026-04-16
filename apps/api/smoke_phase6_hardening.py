"""Phase 6 hardening smoke checks.

Run: python apps/api/smoke_phase6_hardening.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from decimal import Decimal

sys.path.append("apps/api")

from app.services.execution.paper_execution_service import PaperExecutionService
from app.services.governance_service import GovernanceService
from app.services.opportunities.repository import OpportunityRepository
from app.services.portfolio.allocation_service import AllocationService
from app.services.portfolio.ranking_service import RankingService
from app.services.memory_service import MemoryService


def _check_migration_chain() -> tuple[bool, list[str]]:
    versions_dir = Path("apps/api/alembic/versions")
    revisions: dict[str, str | None] = {}

    for file in versions_dir.glob("*.py"):
        text = file.read_text(encoding="utf-8")
        rev_match = re.search(r'revision:\s*str\s*=\s*"([^"]+)"', text)
        down_match = re.search(r'down_revision:\s*Union\[str, None\]\s*=\s*(None|"[^"]+")', text)
        if not rev_match:
            continue
        rev = rev_match.group(1)
        if not down_match:
            down = None
        else:
            down_raw = down_match.group(1)
            down = None if down_raw == "None" else down_raw.strip('\"')
        revisions[rev] = down

    heads = [rev for rev in revisions if rev not in set(d for d in revisions.values() if d)]
    if len(heads) != 1:
        return False, []

    ordered: list[str] = []
    current = heads[0]
    while current:
        ordered.append(current)
        current = revisions.get(current)
    ordered = list(reversed(ordered))

    ok = len(ordered) == len(revisions)
    return ok, ordered


def run() -> None:
    governance = GovernanceService()
    t1 = governance.transition("YELLOW", "SOURCE_STALE")
    t2 = governance.transition("RED", "RISK_SPIKE")
    print("TEST1_GOVERNANCE_TRANSITIONS", t1.get("ok") is True and t2.get("ok") is True and governance.get_state()["state"] == "RED")

    repo = OpportunityRepository()
    candidate = {
        "candidate_id": "C-HARD-1",
        "setup_quality": 0.8,
        "regime_fit": 0.7,
        "data_confidence": 0.9,
        "execution_quality_forecast": 0.75,
        "requires_human_review": False,
    }
    ranked = RankingService().rank_batch([candidate], {"C-HARD-1": Decimal("0.8")})
    repo.save_scores("C-HARD-1", ranked[0])
    print("TEST2_RANKING_PERSISTENCE", len(repo.get_scores()) == 1 and repo.get_scores()[0]["candidate_id"] == "C-HARD-1")

    alloc_service = AllocationService()
    alloc_reject = alloc_service.allocate({"candidate_id": "C-HARD-1", "setup_quality": 0.8, "regime_fit": 0.7, "data_confidence": 0.9}, None)
    alloc_ok = alloc_service.allocate({"candidate_id": "C-HARD-1", "setup_quality": 0.8, "regime_fit": 0.7, "data_confidence": 0.9}, {"outcome": "APPROVE", "size_adjustment": 1})
    print("TEST3_ALLOCATION_GUARDS", alloc_reject.get("ok") is False and alloc_ok.get("ok") is True)

    store = {"C-HARD-1": {"decision": "ALLOCATE", "approved_size_usd": 1000}}
    execution = PaperExecutionService(allocation_lookup=lambda cid: store.get(cid))
    rejected_order = execution.place_paper_order({"candidateId": "MISSING", "symbol": "AAPL", "direction": "LONG"})
    accepted_order = execution.place_paper_order({"candidateId": "C-HARD-1", "symbol": "AAPL", "direction": "LONG", "podName": "LiquidityReversalPod", "qty": 1, "price": 100})
    print("TEST4_ORDER_GUARDRAILS", rejected_order.get("ok") is False and accepted_order.get("ok") is True)

    memory = MemoryService()
    memory.write_journal({"journalType": "POST_TRADE_SUMMARY", "summary": "Done", "asset": "AAPL", "pod": "LiquidityReversalPod"})
    memory.store_memory({"memoryType": "EPISODIC", "summary": "lesson", "asset": "AAPL", "pod": "LiquidityReversalPod"})
    memory.generate_review({"positionId": 1, "asset": "AAPL", "pod": "LiquidityReversalPod"})
    search = memory.search_memory({"asset": "AAPL", "query": "lesson"})
    review = memory.get_review_by_position(1)
    print("TEST5_MEMORY_FLOWS", search.get("count", 0) >= 1 and review.get("ok") is True)

    chain_ok, ordered = _check_migration_chain()
    print("TEST6_MIGRATION_CHAIN_SANITY", chain_ok)
    print("MIGRATION_CHAIN", " -> ".join(ordered))


if __name__ == "__main__":
    run()
