from __future__ import annotations

from app.services.opportunities.pods import ContinuationPullbackPod, LiquidityReversalPod, StrategyPod


class PodRegistry:
    def __init__(self) -> None:
        self._pods: dict[str, StrategyPod] = {}

    def register(self, pod: StrategyPod) -> None:
        self._pods[pod.pod_name] = pod

    def list_pods(self) -> list[StrategyPod]:
        return list(self._pods.values())


registry = PodRegistry()
registry.register(LiquidityReversalPod())
registry.register(ContinuationPullbackPod())
