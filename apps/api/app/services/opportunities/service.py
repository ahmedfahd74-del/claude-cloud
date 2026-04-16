from __future__ import annotations

from app.services.opportunities.registry import registry
from app.services.opportunities.repository import OpportunityRepository


class OpportunityFactoryService:
    def __init__(self, repository: OpportunityRepository) -> None:
        self.repository = repository

    def scan(self, assets: list[str]) -> dict:
        created: list[dict] = []
        for asset in assets:
            for pod in registry.list_pods():
                candidate = pod.generate(asset)
                self.repository.save_candidate(candidate)
                created.append(candidate.to_dict())

        return {
            "scanned_assets": assets,
            "candidate_count": len(created),
            "candidates": created,
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def list_candidates(self) -> list[dict]:
        return self.repository.list_candidates()

    def get_candidate(self, candidate_id: str) -> dict | None:
        return self.repository.get_candidate(candidate_id)
