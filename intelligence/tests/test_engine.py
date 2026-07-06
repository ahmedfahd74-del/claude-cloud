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
from ia_sr.levels import Level, LevelBook, power_pick
from ia_sr.portfolio import PortfolioController, factors
from ia_sr.probability import evaluate as prob_eval
from ia_sr.regime import compute_regime, mode_adjust, trend_sign
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

    def test_merge_keeps_frozen_identity(self):
        # V3 stability: a same-side swing inside the merge radius is the SAME
        # institutional object — it adds evidence but must NOT move the level's
        # frozen identity price (the old v2.0.9 snap-to-extreme was the drift bug).
        b = self._book()
        b.add(100.0, True, 0, 1.0, 0.6)
        b.add(100.3, True, 5, 1.0, 0.6)     # higher high, same cluster
        self.assertEqual(len(b.levels), 1)
        self.assertEqual(b.levels[0].price, 100.0, "identity price must stay FROZEN")
        self.assertGreater(b.levels[0].touches, 0.0, "repeat swing counts as evidence")
        s = self._book()
        s.add(50.0, False, 0, 1.0, 0.6)
        s.add(49.8, False, 5, 1.0, 0.6)     # lower low, same cluster
        self.assertEqual(s.levels[0].price, 50.0, "support identity must stay FROZEN")

    def test_eviction_protects_range_boundaries(self):
        # v2.0.9 parity: the highest/lowest unbroken levels (structural
        # extremes) survive eviction even with the weakest scores.
        b = self._book()                     # cap = 3
        b.add(100.0, False, 0, 1.0, 0.6)     # range low
        b.add(110.0, True, 1, 1.0, 0.6)
        b.add(120.0, True, 2, 1.0, 0.6)
        b.add(130.0, True, 3, 1.0, 0.6)      # range high → over cap
        prices = [lv.price for lv in b.levels]
        self.assertEqual(len(b.levels), 3)
        self.assertIn(100.0, prices, "range low must survive")
        self.assertIn(130.0, prices, "range high must survive")


class TestPowerLine(unittest.TestCase):
    def _books(self):
        h4 = LevelBook(tf="4h", weight=0.60, tf_minutes=240, base_minutes=60, atr_tf=1.0)
        w = LevelBook(tf="1w", weight=1.00, tf_minutes=10080, base_minutes=60, atr_tf=4.0)
        m5 = LevelBook(tf="5m", weight=0.30, tf_minutes=5, base_minutes=60, atr_tf=0.2)
        return h4, w, m5

    def test_trend_side_prefers_launch_level(self):
        h4, w, m5 = self._books()
        h4.add(101.0, True, 0, 1.0, 0.6)    # ceiling just above
        h4.add(98.0, False, 0, 1.0, 0.6)    # launch shelf below (farther)
        pw = power_pick([h4, w], close=100.0, p_atr=1.0, htf_bull=True,
                        htf_bear=False, mom=0.5, base_minutes=60)
        self.assertIsNotNone(pw)
        self.assertEqual(pw.price, 98.0, "BULL bias must pick the launch level below")
        self.assertFalse(pw.is_res)

    def test_sub_institutional_tfs_excluded(self):
        h4, w, m5 = self._books()
        m5.add(100.1, False, 0, 1.0, 0.6)   # nearest, but 5m = not a candidate
        h4.add(99.0, False, 0, 1.0, 0.6)
        pw = power_pick([h4, m5], close=100.0, p_atr=1.0, htf_bull=True,
                        htf_bear=False, mom=0.0, base_minutes=60)
        self.assertEqual(pw.price, 99.0, "5m level must never be the Power Line")

    def test_status_retest_after_flip(self):
        h4, w, m5 = self._books()
        h4.add(100.5, True, 0, 1.0, 0.6)    # resistance, price above → broken side
        pw = power_pick([h4], close=101.0, p_atr=1.0, htf_bull=True,
                        htf_bear=False, mom=0.0, base_minutes=60)
        self.assertEqual(pw.status, "RETEST LIKELY")


class TestAdaptiveMode(unittest.TestCase):
    def test_auto_strict_bounds_and_presets(self):
        regs = compute_regime(mk_bars([100 + (i % 3) * 0.1 for i in range(120)]))
        st = regs[-1]
        self.assertTrue(-10.0 <= st.auto_strict <= 10.0)
        self.assertTrue(0.0 <= st.eff_ratio <= 1.0)
        pa, sa, qa, wick = mode_adjust("Adaptive (Auto)", st)
        self.assertAlmostEqual(pa, st.auto_strict * 0.8)
        self.assertTrue(0.6 <= wick <= 1.0)
        self.assertEqual(mode_adjust("Conservative", st), (5.0, 10.0, 8.0, 1.0))
        self.assertEqual(mode_adjust("Ultra Aggressive", st), (-10.0, -20.0, -14.0, 0.6))


class TestPeriodExtremes(unittest.TestCase):
    def test_daily_levels_exist_without_swing_confirmation(self):
        # Monotonic daily data has no confirmable swings — the daily book must
        # still hold levels via prev-period extremes (Pine v2.0.6 parity).
        base = mk_bars([100 + 0.05 * i for i in range(240)], spread=0.2,
                       t0=1_700_000_000, step=3600)
        daily = mk_bars([100 + 1.2 * k for k in range(45)], spread=0.5,
                        t0=1_700_000_000 - 44 * 86400 + 240 * 3600, step=86400)
        cfg = ScanConfig(symbols=["X"], history_bars=240, base_tf="1h", exec_tf="1h",
                         level_tfs=["1d", "4h", "1h"])
        a = analyze("X", {"1h": base, "1d": daily, "4h": aggregate(base, 240)}, cfg)
        dbook = next(b for b in a.books if b.tf == "1d")
        self.assertTrue(dbook.levels, "period extremes must seed the daily book")
        self.assertIsInstance(a.sweep_pools, list)


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


class TestTiersAndReport(unittest.TestCase):
    def _scan(self):
        from ia_sr.portfolio import PortfolioController
        feed = SyntheticFeed(total_bars=20000)
        cfg = ScanConfig(symbols=["EURUSD", "BTCUSD", "XAUUSD"], history_bars=400)
        pc = PortfolioController()
        return scan(feed, cfg, portfolio=pc), pc, cfg

    def test_three_tier_output(self):
        result, _, cfg = self._scan()
        for o in result.all_ranked:
            self.assertIn(o.tier, ("A", "B", "C"))
            self.assertTrue(0.0 <= o.gate_score <= 100.0)
        self.assertEqual(result.watch,
                         [o for o in result.all_ranked if o.tier == "B"][:cfg.top_n])
        self.assertTrue(all(o.tier == "A" for o in result.approved))

    def test_session_report_text_and_html(self):
        from ia_sr import report as report_mod
        from ia_sr.learning import LearningEngine
        result, pc, _ = self._scan()
        eng = LearningEngine(":memory:")
        eng.record_pine_payload({"v": 1, "sym": "EURUSD", "tf": "60",
                                 "bias": "SHORT", "bull": 34, "bear": 66,
                                 "tier": "B", "gs": 74, "valid": False,
                                 "power": 1.08})
        rep = report_mod.build(result, pc, eng)
        txt = report_mod.to_text(rep)
        self.assertIn("SESSION REPORT", txt)
        self.assertIn("TIER B — WATCH", txt)
        self.assertIn("PINE PARITY", txt)
        page = report_mod.to_html(rep, refresh_sec=60)
        self.assertIn("<table>", page)
        self.assertIn("refresh' content='60'", page)
        self.assertIn("Pine Parity", page)

    def test_pine_payload_parsed_for_parity(self):
        from ia_sr.learning import LearningEngine
        eng = LearningEngine(":memory:")
        eng.record_pine_payload({"v": 1, "sym": "SOLUSD", "tf": "60",
                                 "bias": "LONG", "bull": 71, "bear": 29,
                                 "tier": "A", "gs": 88, "valid": True,
                                 "entry": 80.2, "power": 79.97})
        latest = eng.pine_latest()
        self.assertIn("SOLUSD", latest)
        self.assertEqual(latest["SOLUSD"]["bias"], "LONG")
        self.assertTrue(latest["SOLUSD"]["valid"])

    def test_feed_registry(self):
        from ia_sr.datafeed import make_feed
        self.assertTrue(make_feed("synthetic").bars("EURUSD", "1h", 10))
        with self.assertRaises(ValueError):
            make_feed("nonexistent")


class TestStructure(unittest.TestCase):
    def test_uptrend_bos_and_labels(self):
        from ia_sr.structure import analyze_structure
        # rising zigzag: each peak higher than the last (HH), each trough higher
        # (HL) → confirmed BOS up, trend +1.
        closes = []
        for k in range(8):
            closes += [100 + 5 * k, 104 + 5 * k, 101 + 5 * k]   # up, peak, pull back
        bars = mk_bars(closes, spread=0.3)
        st = analyze_structure(bars, swing_len=1)
        self.assertEqual(st.trend, 1, "rising zigzag must read as uptrend")
        self.assertTrue(any(e.kind == "BOS" and e.direction == 1 for e in st.events))
        self.assertTrue(any(s.label == "HH" for s in st.swings))

    def test_choch_on_reversal(self):
        from ia_sr.structure import analyze_structure
        up = []
        for k in range(6):
            up += [100 + 5 * k, 104 + 5 * k, 101 + 5 * k]
        down = []
        top = up[-1]
        for k in range(6):
            down += [top - 5 * k, top - 4 - 5 * k, top - 1 - 5 * k]
        bars = mk_bars(up + down, spread=0.3)
        st = analyze_structure(bars, swing_len=1)
        self.assertTrue(any(e.kind == "CHoCH" for e in st.events),
                        "a trend reversal must produce a CHoCH")


class TestMethodology(unittest.TestCase):
    def test_gates_in_order_and_shapes(self):
        from ia_sr.methodology import evaluate_methodology
        feed = SyntheticFeed(total_bars=30000)
        cfg = ScanConfig(symbols=["EURUSD"])
        bt = {tf: feed.bars("EURUSD", tf, cfg.history_bars if tf == cfg.base_tf else 400)
              for tf in {cfg.base_tf, *cfg.level_tfs}}
        from ia_sr.analysis import analyze
        a = analyze("EURUSD", bt, cfg)
        mr = a.methodology
        self.assertIn(mr.tier, ("A", "B", "C"))
        self.assertEqual([s.n for s in mr.steps], list(range(1, len(mr.steps) + 1)),
                         "steps must be gated in order 1..n")
        # Step 1 is always evaluated; a later step only exists if earlier passed
        if len(mr.steps) >= 2:
            self.assertTrue(mr.steps[0].passed, "Step 2 present ⇒ Step 1 passed")
        # A tradeable tier must carry a full structural plan with monotonic TPs
        if mr.tier in ("A", "B") and mr.entry is not None:
            d = 1 if mr.bias == "LONG" else -1
            self.assertTrue((mr.tp1 - mr.entry) * d > 0 < (mr.tp3 - mr.tp1) * d)
            self.assertGreater(mr.rr, 0.0)

    def test_no_daily_interaction_rejects_at_step1(self):
        from ia_sr.methodology import evaluate_methodology
        from ia_sr.levels import LevelBook
        # a Daily book whose only level is far from price → outside any IIZ
        book = LevelBook(tf="1d", weight=0.8, tf_minutes=1440, base_minutes=15, atr_tf=1.0)
        book.add(1000.0, True, 0, 1.0, 0.6)
        bars = mk_bars([100 + 0.1 * i for i in range(300)])
        mr = evaluate_methodology({"15m": bars, "1d": mk_bars([100] * 60)}, book, ScanConfig())
        self.assertFalse(mr.active)
        self.assertEqual(mr.tier, "C")
        self.assertIn("Daily", mr.reject_reason)


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
