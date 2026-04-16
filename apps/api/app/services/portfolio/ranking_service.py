from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RankingWeights:
    setup_quality: Decimal = Decimal("0.22")
    regime_fit: Decimal = Decimal("0.18")
    data_confidence: Decimal = Decimal("0.14")
    execution_quality: Decimal = Decimal("0.12")
    portfolio_fit: Decimal = Decimal("0.14")
    historical_expectancy: Decimal = Decimal("0.14")
    fragility_penalty: Decimal = Decimal("0.10")


class RankingService:
    def __init__(self, weights: RankingWeights | None = None) -> None:
        self.weights = weights or RankingWeights()

    def compute_final_score(self, candidate: dict, portfolio_fit: Decimal) -> Decimal:
        sq = Decimal(str(candidate.get("setup_quality", 0)))
        rf = Decimal(str(candidate.get("regime_fit", 0)))
        dc = Decimal(str(candidate.get("data_confidence", 0)))
        eq = Decimal(str(candidate.get("execution_quality_forecast", 0)))
        he = Decimal("0.65")
        fragility = Decimal("0.30") if candidate.get("requires_human_review") else Decimal("0.15")

        score = (
            self.weights.setup_quality * sq
            + self.weights.regime_fit * rf
            + self.weights.data_confidence * dc
            + self.weights.execution_quality * eq
            + self.weights.portfolio_fit * portfolio_fit
            + self.weights.historical_expectancy * he
            - self.weights.fragility_penalty * fragility
        )
        return score.quantize(Decimal("0.001"))

    def rank_batch(self, candidates: list[dict], portfolio_fit_map: dict[str, Decimal]) -> list[dict]:
        ranked = []
        for candidate in candidates:
            c_id = candidate["candidate_id"]
            pfit = portfolio_fit_map.get(c_id, Decimal("0.5"))
            final_score = self.compute_final_score(candidate, pfit)
            ranked.append(
                {
                    "candidate_id": c_id,
                    "setup_quality": Decimal(str(candidate.get("setup_quality", 0))),
                    "regime_fit": Decimal(str(candidate.get("regime_fit", 0))),
                    "data_confidence": Decimal(str(candidate.get("data_confidence", 0))),
                    "execution_quality": Decimal(str(candidate.get("execution_quality_forecast", 0))),
                    "portfolio_fit": pfit,
                    "historical_expectancy": Decimal("0.65"),
                    "fragility": Decimal("0.30") if candidate.get("requires_human_review") else Decimal("0.15"),
                    "final_score": final_score,
                }
            )

        ranked.sort(key=lambda row: row["final_score"], reverse=True)
        for idx, row in enumerate(ranked, start=1):
            row["rank_in_batch"] = idx
        return ranked
