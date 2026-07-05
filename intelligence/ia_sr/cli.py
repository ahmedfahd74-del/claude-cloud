"""Command-line interface.

    python -m ia_sr scan      [--feed NAME] [--symbols A,B] [--top N] [--json]
    python -m ia_sr report    [--feed NAME] [--out report.html]   # session report
    python -m ia_sr dashboard [--feed NAME] [--port 8899] [--interval 300]
    python -m ia_sr live      [--feed yfinance] [--interval 900]  # continuous loop
    python -m ia_sr resolve   [--db PATH]      # settle open signals, update calibration
    python -m ia_sr calibration [--db PATH]    # expected vs realised win rate
    python -m ia_sr webhook   [--port 8787]    # receive Pine JSON exports
"""
from __future__ import annotations

import argparse
import json
import time

from . import report as report_mod
from .config import ScanConfig
from .datafeed import FEEDS, make_feed
from .learning import LearningEngine
from .portfolio import PortfolioController
from .scanner import scan


def _feed(name: str):
    return make_feed(name)


def _cfg_from(args) -> ScanConfig:
    cfg = ScanConfig()
    if getattr(args, "symbols", ""):
        cfg.symbols = [s.strip().upper() for s in args.symbols.split(",")]
    if getattr(args, "top", None):
        cfg.top_n = args.top
    return cfg


def _run_session(args, feed=None):
    """One full session pass: scan -> resolve -> report. Returns the report."""
    cfg = _cfg_from(args)
    learning = LearningEngine(args.db) if args.db else None
    controller = PortfolioController()
    result = scan(feed or _feed(args.feed), cfg, learning=learning,
                  portfolio=controller)
    if learning is not None:
        try:
            learning.resolve_open(feed or _feed(args.feed), cfg.base_tf,
                                  cfg.tf_minutes(cfg.base_tf))
        except Exception:
            pass  # resolution must never kill a report
    return report_mod.build(result, controller, learning)


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
        plan = (f"entry {_fmt(o.entry)} sl {_fmt(o.stop)} tp {_fmt(o.tp1)}" if o.valid
                else f"WATCH · entry {_fmt(o.entry)} sl {_fmt(o.stop)}" if o.tier == "B"
                else "no trade (" + ", ".join(o.fail_reasons[:3] or [o.state]) + ")")
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


def cmd_report(args) -> None:
    rep = _run_session(args)
    print(report_mod.to_text(rep))
    if args.out:
        with open(args.out, "w") as f:
            f.write(report_mod.to_html(rep))
        print(f"\nHTML report written to {args.out}")


def cmd_dashboard(args) -> None:
    """Watchlist dashboard: serves the session report, rescanning on a TTL."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    feed = _feed(args.feed)
    cache = {"html": b"", "ts": 0.0}

    def render() -> bytes:
        rep = _run_session(args, feed=feed)
        return report_mod.to_html(rep, refresh_sec=max(args.interval, 30)).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — stdlib API
            if self.path not in ("/", "/index.html"):
                self.send_response(404)
                self.end_headers()
                return
            if time.time() - cache["ts"] > args.interval:
                try:
                    cache["html"] = render()
                    cache["ts"] = time.time()
                except Exception as exc:   # keep serving the last good page
                    if not cache["html"]:
                        cache["html"] = f"<pre>scan failed: {exc}</pre>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(cache["html"])

        def log_message(self, fmt, *a):  # quiet
            pass

    print(f"IA-SR dashboard on http://localhost:{args.port} "
          f"(feed={args.feed}, rescan every {args.interval}s)")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


def cmd_live(args) -> None:
    """Continuous institutional loop: scan -> record -> resolve -> report."""
    feed_name = args.feed
    n = 0
    while True:
        n += 1
        start = time.time()
        try:
            rep = _run_session(args, feed=_feed(feed_name))  # fresh feed = fresh data
            if args.out:
                with open(args.out, "w") as f:
                    f.write(report_mod.to_html(rep, refresh_sec=args.interval))
            s = rep.stats or {}
            print(f"[{time.strftime('%H:%M:%S')}] pass {n}: "
                  f"{len(rep.execute)} execute, {len(rep.watch)} watch, "
                  f"{s.get('open', 0)} open, {s.get('resolved', 0)} resolved"
                  f"{' -> ' + args.out if args.out else ''}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[{time.strftime('%H:%M:%S')}] pass {n} FAILED: {exc}")
        try:
            time.sleep(max(30.0, args.interval - (time.time() - start)))
        except KeyboardInterrupt:
            print("\nlive loop stopped")
            return


def cmd_backtest(args) -> None:
    from . import backtest as bt_mod
    cfg = _cfg_from(args)
    result = bt_mod.run(_feed(args.feed), cfg, history=args.history,
                        stride=args.stride, warmup=args.warmup)
    s = result.summary()
    print("═" * 64)
    print("IA-SR METHODOLOGY VALIDATION  (no optimisation — robustness only)")
    print("═" * 64)
    print(f"symbols           {len(cfg.symbols)}  ({', '.join(cfg.symbols[:8])}{'…' if len(cfg.symbols) > 8 else ''})")
    print(f"evaluated points  {s['evaluated_points']}")
    print(f"opportunities     {s['opportunities']}   (filled {s['filled']}, closed {s['closed']})")
    print(f"trade frequency   {s['opportunities'] / max(len(cfg.symbols), 1):.1f} per symbol")
    wr = s['win_rate']
    print(f"win rate          {wr:.1f}%" if wr is not None else "win rate          —")
    arr = s['avg_planned_rr']
    print(f"avg planned R:R   {arr:.2f}" if arr is not None else "avg planned R:R   —")
    ar = s['avg_realised_r']
    print(f"avg realised R    {ar:+.2f}R" if ar is not None else "avg realised R    —")
    print(f"expectancy        {s['expectancy_r']:+.3f}R / trade" if s['expectancy_r'] is not None else "expectancy        —")
    print(f"max drawdown      {s['max_drawdown_r']:.2f}R")
    ah = s['avg_hold_bars']
    print(f"avg hold          {ah:.0f} {cfg.exec_tf} bars" if ah is not None else "avg hold          —")
    ta, tb = s['tierA_pct'], s['tierB_pct']
    print(f"tier mix          A {ta:.0f}%   B {tb:.0f}%" if ta is not None else "tier mix          —")
    print("─" * 64)
    print("rejection reasons (why setups were filtered):")
    for reason, cnt in s['reject_reasons'].items():
        print(f"  {cnt:>6}  {reason}")
    if not s['reject_reasons']:
        print("  (none recorded)")
    print("═" * 64)
    if args.json:
        import json
        print(json.dumps(s, indent=2, default=str))


def cmd_ablation(args) -> None:
    import json as _json
    from . import ablation as ab
    cfg = _cfg_from(args)
    study = ab.run_study(_feed(args.feed), cfg, history=args.history,
                         stride=args.stride, warmup=args.warmup)
    rep = ab.full_report(study, cfg)

    def _f(x, fmt="{:.1f}", dash="—"):
        return dash if x is None else fmt.format(x)

    print("═" * 78)
    print("IA-SR METHODOLOGY ABLATION STUDY (one pass, rule-level instrumentation)")
    print("═" * 78)
    print(f"evaluated points {rep['evaluated_points']} · directional candidates "
          f"{rep['candidates']} · resolved {rep['resolved']}")
    print("\nQ1 · FUNNEL — first failing rule (methodology order):")
    print(f"  {'passed ALL rules':<26}{rep['passed_all']:>7}")
    for k in ab.RULE_ORDER:
        print(f"  step {ab.STEP_OF[k]} · {k:<18}{rep['funnel_first_fail'][k]:>7}"
              f"   (would-have-won: {rep['lost_winners_by_step'][k]})")
    print("\nQ3-5 · ABLATIONS — remove one rule at a time:")
    print(f"  {'variant':<30}{'trades':>7}{'/1k bars':>9}{'win%':>7}{'expect R':>10}{'maxDD':>8}")
    base = rep['variants']['FULL (all rules)']
    for name, v in rep['variants'].items():
        print(f"  {name:<30}{v['trades']:>7}{v['per_1k_bars']:>9.2f}"
              f"{_f(v['win_rate']):>7}{_f(v['expectancy_r'], '{:+.3f}'):>10}"
              f"{v['max_dd_r']:>8.1f}")
    print("\nQ6 · CONFUSION MATRIX (vs FULL chain):")
    cm = rep['confusion_matrix']
    print(f"                 WIN      LOSS")
    print(f"  accepted   {cm['accepted_win']:>7}  {cm['accepted_loss']:>8}")
    print(f"  rejected   {cm['rejected_win']:>7}  {cm['rejected_loss']:>8}   "
          f"(rejected winners = missed profit; accepted losers = filter misses)")
    print("\nQ7 · PER MARKET (SIMPLE chain: iiz+htf2+sweep+bos):")
    for mkt, v in rep['per_market_simple'].items():
        print(f"  {mkt:<8} trades {v['trades']:>5}  win% {_f(v['win_rate'])}"
              f"  expect {_f(v['expectancy_r'], '{:+.3f}')}R  maxDD {v['max_dd_r']:.1f}R")
    print("\nQ8 · HTF VOTE COMBINATIONS (which timeframes agreed, SIMPLE chain):")
    for k, v in sorted(rep['htf_combo'].items(), key=lambda kv: -kv[1]['n']):
        print(f"  {k:<12} n {v['n']:>5}  win% {_f(v['win_rate'])}"
              f"  expect {_f(v['expectancy'], '{:+.3f}')}R")
    print("\nQ9 · LOSER ATTRIBUTION (SIMPLE-chain losers, n="
          f"{rep['losers_analyzed']}):")
    for k, v in rep['loser_attribution'].items():
        print(f"  {k:<18}{v:>6}")
    print("═" * 78)
    if args.json:
        print(_json.dumps(rep, indent=2, default=str))
    if args.out:
        with open(args.out, "w") as f:
            _json.dump(rep, f, indent=2, default=str)
        print(f"raw JSON → {args.out}")


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

    feeds = sorted(FEEDS)

    p = sub.add_parser("scan", help="market-wide scan + ranking")
    p.add_argument("--feed", default="synthetic", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--db", default="ia_sr.db")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("report", help="institutional session report (text + HTML)")
    p.add_argument("--feed", default="synthetic", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--db", default="ia_sr.db")
    p.add_argument("--out", default="report.html")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("dashboard", help="live watchlist dashboard (auto-rescan)")
    p.add_argument("--feed", default="synthetic", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--db", default="ia_sr.db")
    p.add_argument("--port", type=int, default=8899)
    p.add_argument("--interval", type=int, default=300)
    p.set_defaults(fn=cmd_dashboard)

    p = sub.add_parser("live", help="continuous scan/record/resolve loop")
    p.add_argument("--feed", default="yfinance", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--db", default="ia_sr.db")
    p.add_argument("--interval", type=int, default=900)
    p.add_argument("--out", default="report.html")
    p.set_defaults(fn=cmd_live)

    p = sub.add_parser("backtest", help="validate the methodology on history")
    p.add_argument("--feed", default="synthetic", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--history", type=int, default=4000)
    p.add_argument("--stride", type=int, default=4)
    p.add_argument("--warmup", type=int, default=400)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_backtest)

    p = sub.add_parser("ablation", help="rule-level ablation study of the methodology")
    p.add_argument("--feed", default="synthetic", choices=feeds)
    p.add_argument("--symbols", default="")
    p.add_argument("--history", type=int, default=3500)
    p.add_argument("--stride", type=int, default=4)
    p.add_argument("--warmup", type=int, default=400)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", default="")
    p.set_defaults(fn=cmd_ablation)

    p = sub.add_parser("resolve", help="settle open signals against fresh bars")
    p.add_argument("--feed", default="synthetic", choices=feeds)
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
