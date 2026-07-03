"""Engine tests — pure stdlib unittest, run with:  python -m unittest discover -s tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_sr.analysis import analyze
from ia_sr.config import ScanConfig
from ia_sr.datafeed import SyntheticFeed, aggregate
from ia_sr.indicators import Bar, atr, clamp, ema, safe_div, sma
from ia_sr.levels import Level, LevelBook
from ia_sr.portfolio import PortfolioController, factors
from ia_sr.probability import evaluate as prob_eval
from ia_sr.regime import compute_regime, trend_sign
from ia_sr.scanner import scan
from ia_sr.swings import detect_swings


def mk_bars(closes, spread=0.5, t0=1_700_000_000, step=3600, vol=1000.0):
    out = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        hi = max(o, c) + spread
        lo = min(o, c) - spread
        out.append(Bar(t0 + i * step, o, hi, lo, c, vol))
        prev = c
    return out


class TestIndicators(unittest.TestCase):
    def test_sma_ema_atr(self):
        vals = [float(i) for i in range(1, 21)]
        s = sma(vals, 5)
        self.assertAlmostEqual(s[-1], (16 + 17 + 18 + 19 + 20) / 5)
        e = ema(vals, 5)
        self.assertTrue(e[-1] > e[0])
        bars = mk_bars(vals)
        a = atr(bars, 14)
        self.assertTrue(a[-1] > 0)

    def test_helpers(self):
        self.assertEqual(safe_div(1, 0), 0.0)
        self.assertEqual(clamp(5, 0, 3), 3)
        self.assertEqual(trend_sign(0.2), 1)
        self.assertEqual(trend_sign(-0.2), -1)
        self.assertEqual(trend_sign(0.05), 0)


class TestSwings(unittest.TestCase):
    def test_detects_obvious_pivot(self):
        closes = [100 + i for i in range(30)] + [130 - i for i in range(30)]
        bars = mk_bars(closes, spread=0.2)
        regs = compute_regime(bars)
        swings = detect_swings(bars, regs, 3600)
        highs = [s for s in swings if s.is_high]
        self.assertTrue(highs, "swing high at the V-top must be detected")
        top = max(b.high for b in bars)
        self.assertTrue(any(abs(s.price - top) < 1.0 for s in highs))
        # non-repaint: confirmation strictly after the pivot
        self.assertTrue(all(s.confirm_index > s.pivot_index for s in swings))


class TestLevelBook(unittest.TestCase):
    def _book(self):
        return LevelBook(tf="1h", weight=0.45, tf_minutes=60, base_minutes=60,
                         max_levels=3, atr_tf=1.0)

    def test_merge_dedupe(self):
        b = self._book()
        b.add(100.0, True, 0, atr_safe=1.0, ad_merge=0.6)
        b.add(100.3, True, 1, atr_safe=1.0, ad_merge=0.6)   # within merge radius
        self.assertEqual(len(b.levels), 1)

    def test_quality_eviction_keeps_proven_level(self):
        b = self._book()
        b.add(100.0, True, 0, 1.0, 0.6)
        b.levels[0].score = 90.0                            # proven level
        b.add(110.0, True, 1, 1.0, 0.6)
        b.add(120.0, True, 2, 1.0, 0.6)
        b.add(130.0, True, 3, 1.0, 0.6)                     # over cap → evict weakest
        prices = [lv.price for lv in b.levels]
        self.assertIn(100.0, prices, "high-score level must survive (no FIFO)")
        self.assertEqual(len(b.levels), 3)

    def test_polarity_flip_on_break(self):
        b = self._book()
        b.add(100.0, False, 0, 1.0, 0.6)                    # support
        st = compute_regime(mk_bars([99, 98, 97, 96, 95] * 12))[-1]
        bar = Bar(0, 99.5, 99.6, 95.0, 95.0, 0)             # close well below
        b.update_breaks(bar, prev_close=101.0, bar_index=10, st=st)
        self.assertTrue(b.levels[0].is_res, "broken support must flip to resistance")


class TestProbability(unittest.TestCase):
    def test_bounds_and_evidence_consistency(self):
        bars = mk_bars([100 + 0.5 * i for i in range(120)])
        regs = compute_regime(bars)
        from ia_sr.decision import evaluate as dec_eval
        dc = dec_eval(bars, len(bars) - 1, regs[-1], [], 1.0, 1.0, 1.0)
        pb = prob_eval(regs[-1], dc, 1.0, 1.0, 1.0, 1.0, False, False, False, False)
        self.assertTrue(2.0 <= pb.bull_prob <= 98.0)
        self.assertEqual(pb.bull_prob + pb.bear_prob, 100.0)
        self.assertTrue(pb.evidence, "aligned trends must produce evidence")
        self.assertIn("Weekly", pb.evidence_text())


class TestPortfolio(unittest.TestCase):
    def test_fx_factor_extraction(self):
        self.assertEqual(factors("EURUSD", "LONG"), {"EUR": 1, "USD": -1})
        self.assertEqual(factors("BTCUSD", "SHORT"), {"CRYPTO": -1, "BTC": -1})

    def test_correlated_exposure_blocked(self):
        pc = PortfolioController()
        pc.take("EURUSD", "LONG")
        pc.take("GBPUSD", "LONG")       # USD now at -2
        ok, why = pc.can_take("AUDUSD", "LONG")
        self.assertFalse(ok)
        self.assertIn("USD", why)


class TestEndToEnd(unittest.TestCase):
    def test_analyze_and_scan_synthetic(self):
        feed = SyntheticFeed(total_bars=20000)
        cfg = ScanConfig(symbols=["EURUSD", "BTCUSD", "XAUUSD"], history_bars=400)
        bars_by_tf = {tf: feed.bars("EURUSD", tf, 400)
                      for tf in {cfg.base_tf, *cfg.level_tfs}}
        bars_by_tf = {k: v for k, v in bars_by_tf.items() if len(v) >= 40}
        a = analyze("EURUSD", bars_by_tf, cfg)
        self.assertIn(a.probability.bias, ("LONG", "SHORT", "NEUTRAL"))
        self.assertTrue(any(book.levels for book in a.books), "levels must exist")
        self.assertTrue(a.plan.gates, "gates must be evaluated")

        result = scan(feed, cfg)
        self.assertEqual(len(result.all_ranked) + len(result.errors), 3)
        # ranking is monotonic in the sort key
        keys = [o.sort_key for o in result.all_ranked]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_aggregate(self):
        feed = SyntheticFeed(total_bars=1000)
        m5 = feed.bars("EURUSD", "5m", 1000)
        h1 = aggregate(m5, 60)
        self.assertTrue(len(h1) <= len(m5) // 10)
        self.assertAlmostEqual(h1[-1].close, m5[-1].close)


if __name__ == "__main__":
    unittest.main()
