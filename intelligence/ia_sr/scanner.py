"""Global Market Scanner — the capability Pine cannot host.

Runs the full institutional engine per symbol across the configured
timeframes, ranks every opportunity, applies learning-engine calibration and
portfolio exposure control, and returns only the top setups.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .analysis import Analysis, analyze
from .config import ScanConfig
from .datafeed import Feed
from .learning import LearningEngine
from .portfolio import PortfolioController

_QUALITY_RANK = {"Excellent": 5, "High Quality": 4, "Good": 3,
                 "Average": 2, "Poor": 1, "No Trade": 0}


@dataclass
class Opportunity:
    symbol: str
    direction: str
    prob: float
    calibrated_prob: float
    quality: str
    state: str
    valid: bool
    rr: float
    entry: float | None
    stop: float | None
    tp1: float | None
    evidence: str
    fail_reasons: list[str] = field(default_factory=list)
    power_price: float | None = None      # Power Line v2.1 (the ONE level)
    power_status: str = ""
    power_is_res: bool = False

    @property
    def sort_key(self):
        return (self.valid, self.calibrated_prob, _QUALITY_RANK.get(self.quality, 0), self.rr)


@dataclass
class ScanResult:
    approved: list[Opportunity]
    rejected: list[tuple[Opportunity, str]]     # portfolio rejections
    all_ranked: list[Opportunity]
    errors: dict[str, str]


def scan(feed: Feed, cfg: ScanConfig | None = None,
         learning: LearningEngine | None = None,
         portfolio: PortfolioController | None = None) -> ScanResult:
    cfg = cfg or ScanConfig()
    ranked: list[Opportunity] = []
    errors: dict[str, str] = {}
    for symbol in cfg.symbols:
        try:
            bars_by_tf = {}
            for tf in {cfg.base_tf, *cfg.level_tfs}:
                bars = feed.bars(symbol, tf, cfg.history_bars if tf == cfg.base_tf else 400)
                if bars:
                    bars_by_tf[tf] = bars
            a = analyze(symbol, bars_by_tf, cfg)
            ranked.append(_to_opportunity(a, learning))
            if learning is not None:
                learning.record(a, cfg.base_tf)
        except Exception as exc:  # a bad symbol must never kill the scan
            errors[symbol] = str(exc)
    ranked.sort(key=lambda o: o.sort_key, reverse=True)

    # Signal filter: directional, tradeable-quality setups only.
    candidates = [o for o in ranked
                  if o.direction != "NEUTRAL"
                  and _QUALITY_RANK.get(o.quality, 0) >= 4
                  and o.calibrated_prob >= cfg.min_prob][:cfg.top_n]
    controller = portfolio or PortfolioController()
    approved, rejected = controller.select(candidates)
    return ScanResult(approved=approved, rejected=rejected,
                      all_ranked=ranked, errors=errors)


def _to_opportunity(a: Analysis, learning: LearningEngine | None) -> Opportunity:
    prob = a.probability.dir_prob
    cal = learning.calibrate(prob) if learning is not None else prob
    return Opportunity(
        symbol=a.symbol, direction=a.probability.bias,
        prob=prob, calibrated_prob=cal,
        quality=a.probability.quality, state=a.decision.market_state,
        valid=a.plan.valid, rr=a.plan.rr,
        entry=a.plan.entry, stop=a.plan.stop, tp1=a.plan.tp1,
        evidence=a.probability.evidence_text(),
        fail_reasons=a.plan.fail_reasons,
        power_price=a.power.price if a.power else None,
        power_status=a.power.status if a.power else "",
        power_is_res=a.power.is_res if a.power else False,
    )
