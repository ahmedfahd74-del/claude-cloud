from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal


class MemoryService:
    def __init__(self) -> None:
        self._journals: list[dict] = []
        self._memories: list[dict] = []
        self._reviews: list[dict] = []
        self._pod_performance: list[dict] = []
        self._policy_queue: list[dict] = [
            {
                "proposalId": 1,
                "proposalType": "RISK_THRESHOLD",
                "title": "Tighten drawdown clamp in YELLOW",
                "rationale": "Recent review cadence suggests slightly lower tolerance.",
                "status": "PENDING_REVIEW",
                "proposedBy": "review-engine",
                "createdAt": datetime.now(tz=timezone.utc).isoformat(),
                "paperTradingOnly": True,
                "liveExecutionEnabled": False,
            }
        ]

    def _db_handles(self):
        try:
            from app.db.models import DecisionMemory, PodPerformance, PolicyChangeQueue, Position, ReviewReport, TradeJournal
            from app.db.session import SessionLocal

            return SessionLocal, TradeJournal, DecisionMemory, ReviewReport, PodPerformance, PolicyChangeQueue, Position
        except Exception:
            return None, None, None, None, None, None, None

    def write_journal(self, payload: dict) -> dict:
        entry = {
            "journalId": len(self._journals) + 1,
            "journalType": payload.get("journalType", "POST_TRADE_SUMMARY"),
            "asset": payload.get("asset"),
            "pod": payload.get("pod"),
            "summary": payload.get("summary", ""),
            "positionId": payload.get("positionId"),
            "paperOrderId": payload.get("paperOrderId"),
            "candidateId": payload.get("candidateId"),
            "tags": payload.get("tags", []),
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        self._journals.insert(0, entry)

        SessionLocal, TradeJournal, *_ = self._db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    session.add(
                        TradeJournal(
                            position_id=entry.get("positionId"),
                            paper_order_id=entry.get("paperOrderId"),
                            candidate_ref=entry.get("candidateId"),
                            asset=entry.get("asset"),
                            pod_name=entry.get("pod"),
                            journal_type=entry.get("journalType"),
                            summary=entry.get("summary"),
                            event_type=entry.get("journalType"),
                            details=entry.get("summary") or "",
                        )
                    )
                    session.commit()
            except Exception:
                pass

        return {"ok": True, "entry": entry, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def store_memory(self, payload: dict) -> dict:
        record = {
            "memoryId": len(self._memories) + 1,
            "memoryType": payload.get("memoryType", "EPISODIC"),
            "asset": payload.get("asset"),
            "pod": payload.get("pod"),
            "regime": payload.get("regime"),
            "setupFamily": payload.get("setupFamily"),
            "tags": payload.get("tags", []),
            "summary": payload.get("summary", ""),
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        self._memories.insert(0, record)

        SessionLocal, _, DecisionMemory, *_ = self._db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    session.add(
                        DecisionMemory(
                            memory_type=record["memoryType"],
                            asset=record.get("asset"),
                            pod_name=record.get("pod"),
                            regime_label=record.get("regime"),
                            setup_family=record.get("setupFamily"),
                            tags=",".join(record.get("tags", [])),
                            summary=record.get("summary") or "",
                        )
                    )
                    session.commit()
            except Exception:
                pass

        return {"ok": True, "record": record, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def search_memory(self, payload: dict) -> dict:
        query = str(payload.get("query", "")).lower().strip()
        asset = payload.get("asset")
        pod = payload.get("pod")
        regime = payload.get("regime")
        setup_family = payload.get("setupFamily")

        def matches(r: dict) -> bool:
            if asset and r.get("asset") != asset:
                return False
            if pod and r.get("pod") != pod:
                return False
            if regime and r.get("regime") != regime:
                return False
            if setup_family and r.get("setupFamily") != setup_family:
                return False
            if query and query not in str(r.get("summary", "")).lower():
                return False
            return True

        rows = [r for r in self._memories if matches(r)]
        return {"ok": True, "results": rows, "count": len(rows), "paperTradingOnly": True, "liveExecutionEnabled": False}

    def generate_review(self, payload: dict) -> dict:
        process_score = Decimal(str(payload.get("processScore", 0.78))).quantize(Decimal("0.001"))
        execution_score = Decimal(str(payload.get("executionScore", 0.74))).quantize(Decimal("0.001"))
        outcome_score = Decimal(str(payload.get("outcomeScore", 0.70))).quantize(Decimal("0.001"))
        review = {
            "reviewId": len(self._reviews) + 1,
            "positionId": payload.get("positionId"),
            "candidateId": payload.get("candidateId"),
            "asset": payload.get("asset"),
            "pod": payload.get("pod"),
            "processScore": float(process_score),
            "executionScore": float(execution_score),
            "outcomeScore": float(outcome_score),
            "reviewSummary": payload.get("reviewSummary") or "Disciplined execution with one actionable lesson.",
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        self._reviews.insert(0, review)

        SessionLocal, _, _, ReviewReport, *_ = self._db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    session.add(
                        ReviewReport(
                            position_id=review.get("positionId"),
                            candidate_ref=review.get("candidateId"),
                            asset=review.get("asset"),
                            pod_name=review.get("pod"),
                            report_type="TRADE_REVIEW",
                            subject_ref=f"position:{review.get('positionId')}",
                            process_score=process_score,
                            execution_score=execution_score,
                            outcome_score=outcome_score,
                            review_summary=review.get("reviewSummary"),
                            summary=review.get("reviewSummary") or "",
                        )
                    )
                    session.commit()
            except Exception:
                pass

        return {"ok": True, "review": review, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def get_review_by_position(self, position_id: int) -> dict:
        found = next((r for r in self._reviews if r.get("positionId") == position_id), None)
        if not found:
            return {"ok": False, "error": "review_not_found", "positionId": position_id}
        return {"ok": True, "review": found, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def list_reviews(self, candidate_id: str | None = None) -> dict:
        rows = [r for r in self._reviews if (candidate_id is None or r.get("candidateId") == candidate_id)]
        return {"reviews": rows, "count": len(rows), "paperTradingOnly": True, "liveExecutionEnabled": False}

    def aggregate_pod_performance(self) -> dict:
        grouped: dict[tuple, list[dict]] = defaultdict(list)
        for r in self._reviews:
            key = (
                r.get("pod") or "unknown",
                r.get("regime") or "unknown",
                r.get("timeframe") or "unknown",
                r.get("assetClass") or "unknown",
            )
            grouped[key].append(r)

        summaries = []
        for (pod, regime, timeframe, asset_class), rows in grouped.items():
            wins = [1 for row in rows if row.get("outcomeScore", 0) >= 0.6]
            avg_outcome = sum(float(row.get("outcomeScore", 0)) for row in rows) / max(len(rows), 1)
            summary = {
                "pod": pod,
                "regime": regime,
                "timeframe": timeframe,
                "assetClass": asset_class,
                "tradesCount": len(rows),
                "winRate": round(len(wins) / max(len(rows), 1), 3),
                "avgOutcomeScore": round(avg_outcome, 3),
                "computedAt": datetime.now(tz=timezone.utc).isoformat(),
            }
            summaries.append(summary)

        self._pod_performance = sorted(summaries, key=lambda s: s["tradesCount"], reverse=True)

        SessionLocal, _, _, _, PodPerformance, _, _ = self._db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    for row in self._pod_performance:
                        session.add(
                            PodPerformance(
                                pod_name=row["pod"],
                                regime_label=row["regime"],
                                timeframe=row["timeframe"],
                                asset_class=row["assetClass"],
                                trades_count=row["tradesCount"],
                                win_rate=Decimal(str(row["winRate"])),
                                avg_outcome_score=Decimal(str(row["avgOutcomeScore"])),
                            )
                        )
                    session.commit()
            except Exception:
                pass

        return {"summaries": self._pod_performance, "paperTradingOnly": True, "liveExecutionEnabled": False}

    def list_policy_queue(self) -> dict:
        return {
            "items": self._policy_queue,
            "count": len(self._policy_queue),
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }

    def create_policy_proposal(self, payload: dict) -> dict:
        item = {
            "proposalId": len(self._policy_queue) + 1,
            "proposalType": payload.get("proposalType", "PROCESS"),
            "title": payload.get("title", "Untitled policy proposal"),
            "rationale": payload.get("rationale", ""),
            "status": "PENDING_REVIEW",
            "proposedBy": payload.get("proposedBy", "memory-service"),
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
            "paperTradingOnly": True,
            "liveExecutionEnabled": False,
        }
        self._policy_queue.insert(0, item)

        SessionLocal, _, _, _, _, PolicyChangeQueue, _ = self._db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    session.add(
                        PolicyChangeQueue(
                            proposal_type=item["proposalType"],
                            title=item["title"],
                            rationale=item["rationale"],
                            status=item["status"],
                            proposed_by=item["proposedBy"],
                        )
                    )
                    session.commit()
            except Exception:
                pass

        return {"ok": True, "item": item, "paperTradingOnly": True, "liveExecutionEnabled": False}


memory_service = MemoryService()
