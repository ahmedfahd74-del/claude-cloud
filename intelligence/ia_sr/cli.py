"""Command-line interface.

    python -m ia_sr scan [--feed synthetic|yfinance] [--symbols A,B] [--top N] [--json]
    python -m ia_sr resolve [--db PATH]        # settle open signals, update calibration
    python -m ia_sr calibration [--db PATH]    # expected vs realised win rate
    python -m ia_sr webhook [--port 8787]      # receive Pine JSON exports
"""
from __future__ import annotations

import argparse
import json

from .config import ScanConfig
from .datafeed import SyntheticFeed
from .learning import LearningEngine
from .scanner import scan


def _feed(name: str):
    if name == "yfinance":
        from .datafeed import YFinanceFeed
        return YFinanceFeed()
    return SyntheticFeed()


def _fmt(x, digits=5):
    return "—" if x is None else f"{x:.{digits}g}"


def cmd_scan(args) -> None:
    cfg = ScanConfig()
    if args.symbols:
        cfg.symbols = [s.strip().upper() for s in args.symbols.split(",")]
    cfg.top_n = args.top
    learning = LearningEngine(args.db) if args.db else None
    result = scan(_feed(args.feed), cfg, learning=learning)

    if args.json:
        print(json.dumps([o.__dict__ for o in result.all_ranked], indent=2, default=str))
        return

    print(f"{'SYMBOL':<8} {'DIR':<7} {'PROB':>5} {'CAL':>5} {'QUALITY':<13} "
          f"{'STATE':<22} {'R:R':>5} {'POWER':<22}  PLAN")
    for o in result.all_ranked:
        plan = (f"entry {_fmt(o.entry)} sl {_fmt(o.stop)} tp {_fmt(o.tp1)}"
                if o.valid else "no trade (" + ", ".join(o.fail_reasons[:3]) + ")")
        power = ("—" if o.power_price is None else
                 f"{_fmt(o.power_price)} {'R' if o.power_is_res else 'S'} {o.power_status}")
        print(f"{o.symbol:<8} {o.direction:<7} {o.prob:>4.0f}% {o.calibrated_prob:>4.0f}% "
              f"{o.quality:<13} {o.state:<22} {o.rr:>5.1f} {power:<22.22}  {plan}")
    print(f"\nTOP SETUPS (after signal filter + portfolio control): {len(result.approved)}")
    for o in result.approved:
        print(f"  {o.symbol} {o.direction} {o.calibrated_prob:.0f}% {o.quality}"
              f" | entry {_fmt(o.entry)} sl {_fmt(o.stop)} tp1 {_fmt(o.tp1)} rr {o.rr:.1f}")
        print(f"    why: {o.evidence}")
    for o, why in result.rejected:
        print(f"  [skipped] {o.symbol} {o.direction} — {why}")
    if result.errors:
        print(f"\nerrors: {result.errors}")


def cmd_resolve(args) -> None:
    cfg = ScanConfig()
    eng = LearningEngine(args.db)
    n = eng.resolve_open(_feed(args.feed), cfg.base_tf, cfg.tf_minutes(cfg.base_tf))
    print(f"resolved {n} signal(s)")
    cmd_calibration(args)


def cmd_calibration(args) -> None:
    eng = LearningEngine(args.db)
    print(f"{'BUCKET':<8} {'N':>4} {'EXPECTED':>9} {'ACTUAL':>7} {'GAP':>7}")
    for b in eng.buckets():
        if b.n:
            print(f"{b.label:<8} {b.n:>4} {b.expected:>8.0f}% {b.actual:>6.0f}% {b.gap:>+6.0f}%")
        else:
            print(f"{b.label:<8} {b.n:>4} {'—':>9} {'—':>7} {'—':>7}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ia_sr", description="IA-SR intelligence layer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="market-wide scan + ranking")
    p.add_argument("--feed", default="synthetic", choices=["synthetic", "yfinance"])
    p.add_argument("--symbols", default="")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--db", default="ia_sr.db")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("resolve", help="settle open signals against fresh bars")
    p.add_argument("--feed", default="synthetic", choices=["synthetic", "yfinance"])
    p.add_argument("--db", default="ia_sr.db")
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("calibration", help="expected vs realised win rate")
    p.add_argument("--db", default="ia_sr.db")
    p.set_defaults(fn=cmd_calibration)

    p = sub.add_parser("webhook", help="receive Pine JSON exports")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--db", default="ia_sr.db")
    p.set_defaults(fn=lambda a: __import__("ia_sr.webhook", fromlist=["serve"]).serve(a.port, a.db))

    args = ap.parse_args(argv)
    args.fn(args)
