"""Phase 5 memory layer smoke checks.

Run: python apps/api/smoke_phase5_memory.py
"""

from __future__ import annotations

import sys

sys.path.append("apps/api")

from app.services.memory_service import MemoryService


def run() -> None:
    svc = MemoryService()

    journal = svc.write_journal(
        {
            "journalType": "POST_TRADE_SUMMARY",
            "asset": "AAPL",
            "pod": "LiquidityReversalPod",
            "summary": "Executed according to plan.",
            "candidateId": "LRP-AAPL-001",
            "positionId": 1,
            "paperOrderId": 1001,
            "tags": ["discipline"],
        }
    )
    print("TEST1_JOURNAL_WRITE", journal.get("ok") is True and journal["entry"]["journalType"] == "POST_TRADE_SUMMARY")

    svc.store_memory(
        {
            "memoryType": "EPISODIC",
            "asset": "AAPL",
            "pod": "LiquidityReversalPod",
            "regime": "YELLOW",
            "setupFamily": "liquidity_reversal",
            "summary": "VWAP hold improved outcome.",
            "tags": ["vwap", "reclaim"],
        }
    )
    svc.store_memory(
        {
            "memoryType": "SEMANTIC",
            "asset": "BTCUSD",
            "pod": "ContinuationPullbackPod",
            "regime": "YELLOW",
            "setupFamily": "continuation_pullback",
            "summary": "Spread expansion hurt continuation entry quality.",
            "tags": ["spread"],
        }
    )
    search = svc.search_memory({"asset": "AAPL", "query": "vwap"})
    print("TEST2_MEMORY_STORE_SEARCH", search.get("ok") is True and search.get("count", 0) >= 1)

    review = svc.generate_review(
        {
            "positionId": 1,
            "candidateId": "LRP-AAPL-001",
            "asset": "AAPL",
            "pod": "LiquidityReversalPod",
            "processScore": 0.81,
            "executionScore": 0.75,
            "outcomeScore": 0.72,
            "reviewSummary": "Strong process with acceptable execution drift.",
        }
    )
    by_position = svc.get_review_by_position(1)
    print("TEST3_REVIEW_GENERATION_RETRIEVAL", review.get("ok") is True and by_position.get("ok") is True)

    perf = svc.aggregate_pod_performance()
    print("TEST4_POD_PERFORMANCE_AGGREGATION", len(perf.get("summaries", [])) >= 1 and perf["summaries"][0]["pod"] == "LiquidityReversalPod")


if __name__ == "__main__":
    run()
