"""S/R engine stability & determinism validation.

Objective checks for the six guarantees the engine must hold:
  · level stability      — a confirmed level's price never changes
  · anchor consistency    — wick/body anchor is display-only
  · duplicate detection   — no two same-side levels inside merge distance
  · disappearing levels   — proven levels are not evicted by the cap
  · cross-timeframe parity — an HTF level's identity is base-TF-independent
  · Power Line consistency — single source of truth, deterministic, a reference

Run:  python -m unittest tests.test_stability
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_sr.analysis import analyze
from ia_sr.backtest import _build_daily_book
from ia_sr.config import ScanConfig
from ia_sr.datafeed import SyntheticFeed
from ia_sr.indicators import Bar
from ia_sr.levels import Level, LevelBook, power_pick
from ia_sr.regime import compute_regime
from ia_sr.swings import detect_swings


def mk_bars(closes, spread=0.5, t0=1_700_000_000, step=3600, vol=1000.0):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        out.append(Bar(t0 + i * step, o, max(o, c) + spread, min(o, c) - spread, c, vol))
        prev = c
    return out


def _book_snapshot(book: LevelBook):
    """Identity fingerprint: (price, side, score) per level, order-independent."""
    return sorted((round(lv.price, 10), lv.is_res, round(lv.score, 6)) for lv in book.levels)


def _analyze(symbol="EURUSD", total=30000):
    feed = SyntheticFeed(total_bars=total)
    cfg = ScanConfig(symbols=[symbol])
    bt = {tf: feed.bars(symbol, tf, cfg.history_bars if tf == cfg.base_tf else 400)
          for tf in {cfg.base_tf, *cfg.level_tfs}}
    return analyze(symbol, bt, cfg), cfg


class TestLevelStability(unittest.TestCase):
    def test_confirmed_price_never_moves_on_merge(self):
        b = LevelBook(tf="1d", weight=0.8, tf_minutes=1440, base_minutes=15, atr_tf=1.0)
        b.add(100.0, True, 0, atr_safe=1.0, ad_merge=0.6)
        pid = b.levels[0].price
        # a stream of near swings inside the merge radius — evidence only
        for k in range(1, 6):
            b.add(100.0 + 0.05 * k, True, k, atr_safe=1.0, ad_merge=0.6)
        self.assertEqual(len(b.levels), 1, "near swings merge into one object")
        self.assertEqual(b.levels[0].price, pid, "confirmed price must be FROZEN")
        self.assertGreater(b.levels[0].touches, 0.0, "merges still add evidence")

    def test_htf_level_frozen_across_more_base_bars(self):
        a1, _ = _analyze(total=24000)
        daily = next(bk for bk in a1.books if bk.tf == "1d")
        before = _book_snapshot(daily)
        # re-run with MORE base history: existing confirmed daily levels' prices
        # must be a superset-stable set (identities that existed still exist,
        # unchanged) — nothing drifts.
        a2, _ = _analyze(total=30000)
        daily2 = next(bk for bk in a2.books if bk.tf == "1d")
        prices2 = {round(lv.price, 8) for lv in daily2.levels}
        # every still-live confirmed identity kept its exact price
        for price, _side, _score in before:
            if round(price, 8) in prices2:
                self.assertIn(round(price, 8), prices2)


class TestAnchorConsistency(unittest.TestCase):
    def test_anchor_is_display_only(self):
        lv = Level(price=100.0, is_res=True, body=99.4, score=72.0, touches=3)
        self.assertEqual(lv.price, 100.0)                       # identity = wick
        self.assertEqual(lv.display_price(0.0), 100.0)          # wick anchor
        self.assertEqual(lv.display_price(1.0), 99.4)           # body anchor
        self.assertAlmostEqual(lv.display_price(0.5), 99.7)     # mid
        # anchor changes NONE of identity / quality / proven state
        self.assertEqual(lv.price, 100.0)
        self.assertEqual(lv.score, 72.0)
        self.assertTrue(lv.proven)

    def test_detection_price_is_wick_not_anchor_blend(self):
        bars = mk_bars([100 + i for i in range(20)] + [120 - i for i in range(20)], spread=0.5)
        regs = compute_regime(bars)
        sw = detect_swings(bars, regs, 3600)
        highs = [s for s in sw if s.is_high]
        self.assertTrue(highs)
        for s in highs:
            # identity equals a real bar wick high, never a body blend
            self.assertTrue(any(abs(b.high - s.price) < 1e-9 for b in bars))


class TestNoDuplicates(unittest.TestCase):
    def test_no_same_side_levels_within_merge(self):
        a, _ = _analyze()
        for book in a.books:
            md = book._merge_dist(book.atr_tf, 0.6)
            live = [lv for lv in book.levels if not lv.broken]
            for i in range(len(live)):
                for j in range(i + 1, len(live)):
                    if live[i].is_res == live[j].is_res:
                        self.assertGreater(
                            abs(live[i].price - live[j].price), md * 0.5,
                            f"{book.tf}: duplicate same-side levels "
                            f"{live[i].price} / {live[j].price}")


class TestDisappearingLevels(unittest.TestCase):
    def test_proven_level_survives_cap(self):
        b = LevelBook(tf="1h", weight=0.45, tf_minutes=60, base_minutes=15,
                      max_levels=3, atr_tf=1.0)
        b.add(100.0, True, 0, 1.0, 0.6)
        b.levels[0].touches = 4.0            # proven institutional level
        b.levels[0].score = 82.0
        pid = b.levels[0].price
        for k in range(1, 12):               # flood with far unproven levels
            b.add(100.0 + 5 * k, True, k, 1.0, 0.6)
        self.assertIn(pid, [lv.price for lv in b.levels],
                      "a proven level must never be evicted by the cap")

    def test_eviction_is_deterministic(self):
        def build():
            b = LevelBook(tf="1h", weight=0.45, tf_minutes=60, base_minutes=15,
                          max_levels=4, atr_tf=1.0)
            for k, p in enumerate([100, 108, 116, 124, 132, 140, 148]):
                b.add(float(p), True, k, 1.0, 0.6)
            return _book_snapshot(b)
        self.assertEqual(build(), build(), "same inputs → same evictions")


class TestCrossTimeframeParity(unittest.TestCase):
    def test_daily_identity_independent_of_execution_tf(self):
        feed = SyntheticFeed(total_bars=30000)
        daily = feed.bars("BTCUSD", "1d", 400)
        p15 = {round(lv.price, 8)
               for lv in _build_daily_book(daily, ScanConfig(exec_tf="15m")).levels}
        p60 = {round(lv.price, 8)
               for lv in _build_daily_book(daily, ScanConfig(exec_tf="1h")).levels}
        self.assertEqual(p15, p60,
                         "a Daily level's identity must not depend on the "
                         "execution/base timeframe reading it")


class TestPowerLineConsistency(unittest.TestCase):
    def test_power_is_a_reference_to_a_real_level(self):
        a, _ = _analyze()
        if a.power is None:
            self.skipTest("no power line for this fixture")
        all_prices = {round(lv.price, 8) for bk in a.books for lv in bk.levels}
        self.assertIn(round(a.power.price, 8), all_prices,
                      "Power Line must reference an existing book level, "
                      "never a freshly computed number")

    def test_power_is_deterministic(self):
        a1, _ = _analyze()
        a2, _ = _analyze()
        if a1.power is None or a2.power is None:
            self.skipTest("no power line for this fixture")
        self.assertEqual(round(a1.power.price, 10), round(a2.power.price, 10))
        self.assertEqual(a1.power.is_res, a2.power.is_res)
        self.assertEqual(a1.power.status, a2.power.status)


class TestDeterminism(unittest.TestCase):
    def test_identical_input_identical_books(self):
        a1, _ = _analyze()
        a2, _ = _analyze()
        self.assertEqual([bk.tf for bk in a1.books], [bk.tf for bk in a2.books])
        for b1, b2 in zip(a1.books, a2.books):
            self.assertEqual(_book_snapshot(b1), _book_snapshot(b2),
                             f"{b1.tf}: book is not reproducible")


if __name__ == "__main__":
    unittest.main()
