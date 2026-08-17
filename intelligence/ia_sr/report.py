"""Institutional Session Report + Watchlist Dashboard rendering.

One builder consumes a ScanResult (+ optional LearningEngine) and produces a
SessionReport; two renderers emit it as terminal text or a self-contained
dark-theme HTML page (also used by the live dashboard server with an
auto-refresh meta tag). Pure stdlib.
"""
from __future__ import annotations

import html
import time
from dataclasses import dataclass, field

from .portfolio import PortfolioController
from .scanner import Opportunity, ScanResult


@dataclass
class ParityRow:
    symbol: str
    pine_bias: str
    pine_prob: float
    py_bias: str
    py_prob: float
    age_min: float

    @property
    def agree(self) -> bool:
        return self.pine_bias == self.py_bias


@dataclass
class SessionReport:
    generated_ts: int
    execute: list[Opportunity]                  # Tier A after portfolio control
    watch: list[Opportunity]                    # Tier B
    rejected: list[tuple[Opportunity, str]]     # portfolio rejections
    exposure: dict[str, int]
    open_risk_pct: float
    positions: int
    stats: dict | None
    buckets: list | None
    parity: list[ParityRow]
    errors: dict[str, str]
    scanned: int


def build(result: ScanResult, controller: PortfolioController | None = None,
          learning=None) -> SessionReport:
    exposure, risk, npos = {}, 0.0, 0
    if controller is not None:
        exposure = {k: v for k, v in controller.exposure.items() if v}
        risk, npos = controller.open_risk_pct, controller.positions

    stats = buckets = None
    parity: list[ParityRow] = []
    if learning is not None:
        stats = learning.stats()
        buckets = learning.buckets()
        pine = learning.pine_latest()
        now = time.time()
        by_sym = {o.symbol: o for o in result.all_ranked}
        for sym, p in pine.items():
            o = by_sym.get(sym)
            if o is None:
                continue
            pine_prob = p["bull"] if p["bias"] == "LONG" else p["bear"] if p["bias"] == "SHORT" else 50.0
            parity.append(ParityRow(symbol=sym, pine_bias=p["bias"] or "—",
                                    pine_prob=pine_prob or 0.0,
                                    py_bias=o.direction, py_prob=o.prob,
                                    age_min=(now - p["ts"]) / 60.0))

    return SessionReport(
        generated_ts=int(time.time()),
        execute=result.approved, watch=result.watch, rejected=result.rejected,
        exposure=exposure, open_risk_pct=risk, positions=npos,
        stats=stats, buckets=buckets, parity=parity,
        errors=result.errors, scanned=len(result.all_ranked) + len(result.errors),
    )


# --- text renderer -----------------------------------------------------------

def _px(x) -> str:
    return "—" if x is None else f"{x:.6g}"


def _opp_line(o: Opportunity) -> str:
    power = ("—" if o.power_price is None
             else f"{_px(o.power_price)} {'R' if o.power_is_res else 'S'} · {o.power_status}")
    return (f"  {o.symbol:<8} {o.direction:<6} tier {o.tier} ({o.gate_score:.0f})"
            f"  prob {o.prob:.0f}% (cal {o.calibrated_prob:.0f}%)  {o.quality}\n"
            f"           entry {_px(o.entry)}  stop {_px(o.stop)}"
            f"  tp {_px(o.tp1)} / {_px(o.tp2)} / {_px(o.tp3)}  R:R {o.rr:.1f}\n"
            f"           power {power}\n"
            f"           why: {o.evidence or o.state}")


def to_text(r: SessionReport) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(r.generated_ts))
    lines = [f"IA-SR INSTITUTIONAL SESSION REPORT — {ts}",
             f"scanned {r.scanned} symbols · {len(r.execute)} EXECUTE · "
             f"{len(r.watch)} WATCH · {len(r.errors)} errors", ""]

    lines.append(f"TIER A — EXECUTE ({len(r.execute)})")
    lines += [_opp_line(o) for o in r.execute] or ["  none — capital preserved"]
    lines.append("")
    lines.append(f"TIER B — WATCH ({len(r.watch)})")
    for o in r.watch:
        need = ", ".join(o.fail_reasons[:3]) or "—"
        lines.append(f"  {o.symbol:<8} {o.direction:<6} gs {o.gate_score:.0f}"
                     f"  prob {o.prob:.0f}%  needs: {need}")
    if not r.watch:
        lines.append("  none")
    lines.append("")

    lines.append("PORTFOLIO")
    lines.append(f"  positions {r.positions} · open risk {r.open_risk_pct:.1f}%")
    if r.exposure:
        lines.append("  exposure: " + "  ".join(f"{k}{v:+d}" for k, v in sorted(r.exposure.items())))
    for o, why in r.rejected:
        lines.append(f"  [blocked] {o.symbol} {o.direction} — {why}")
    lines.append("")

    if r.stats:
        s = r.stats
        wr = f"{s['win_rate']:.0f}%" if s["win_rate"] is not None else "—"
        ar = f"{s['avg_r']:+.2f}R" if s["avg_r"] is not None else "—"
        lines.append("PERFORMANCE")
        lines.append(f"  signals {s['total']} · open {s['open']} · resolved {s['resolved']}"
                     f" · win rate {wr} · avg {ar}")
        if r.buckets:
            for b in r.buckets:
                if b.n:
                    lines.append(f"  cal {b.label:<6} n={b.n:<4} exp {b.expected:.0f}%"
                                 f" act {b.actual:.0f}% gap {b.gap:+.0f}%")
        lines.append("")

    if r.parity:
        lines.append("PINE PARITY (latest webhook vs this scan)")
        for p in r.parity:
            flag = "OK " if p.agree else "DIVERGES"
            lines.append(f"  {flag} {p.symbol:<8} pine {p.pine_bias} {p.pine_prob:.0f}%"
                         f" vs py {p.py_bias} {p.py_prob:.0f}% ({p.age_min:.0f}m old)")
        lines.append("")

    if r.errors:
        lines.append("ERRORS: " + "; ".join(f"{k}: {v}" for k, v in r.errors.items()))
    return "\n".join(lines)


# --- HTML renderer (dashboard + report file) ----------------------------------

_CSS = """
:root{--bg:#0d1117;--panel:#161b22;--line:#21262d;--txt:#c9d1d9;--dim:#8b949e;
--green:#3fb950;--red:#f85149;--amber:#d29922;--gold:#e3b341;--blue:#58a6ff}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--txt);
font:14px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;padding:24px;max-width:1180px;margin:auto}
h1{font-size:18px;letter-spacing:.06em}h2{font-size:13px;color:var(--dim);
text-transform:uppercase;letter-spacing:.12em;margin:28px 0 10px}
.sub{color:var(--dim);font-size:12px;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
border-radius:8px;overflow:hidden}th{font-size:11px;color:var(--dim);text-transform:uppercase;
letter-spacing:.08em;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}.num{text-align:right}
.long{color:var(--green);font-weight:600}.short{color:var(--red);font-weight:600}
.neutral{color:var(--dim)}.tierA{background:var(--green);color:#04140a;font-weight:700;
padding:2px 8px;border-radius:10px;font-size:11px}.tierB{background:var(--amber);color:#140f02;
font-weight:700;padding:2px 8px;border-radius:10px;font-size:11px}
.power{color:var(--gold)}.why{color:var(--dim);font-size:12px}
.pill{display:inline-block;background:var(--line);border-radius:10px;padding:2px 10px;
margin:2px 4px 2px 0;font-size:12px}.ok{color:var(--green)}.bad{color:var(--red)}
.empty{color:var(--dim);padding:14px;background:var(--panel);border:1px dashed var(--line);
border-radius:8px}
"""


def _h(x) -> str:
    return html.escape(str(x))


def _dir_cls(d: str) -> str:
    return "long" if d == "LONG" else "short" if d == "SHORT" else "neutral"


def _trade_rows(opps: list[Opportunity]) -> str:
    rows = []
    for o in opps:
        power = ("—" if o.power_price is None else
                 f"{_px(o.power_price)} {'R' if o.power_is_res else 'S'} · {_h(o.power_status)}")
        rows.append(
            f"<tr><td><b>{_h(o.symbol)}</b></td>"
            f"<td class='{_dir_cls(o.direction)}'>{_h(o.direction)}</td>"
            f"<td><span class='tier{_h(o.tier)}'>{_h(o.tier)}</span> {o.gate_score:.0f}</td>"
            f"<td class='num'>{o.prob:.0f}% <span class='why'>({o.calibrated_prob:.0f}%)</span></td>"
            f"<td>{_h(o.quality)}</td>"
            f"<td class='num'>{_px(o.entry)}</td><td class='num'>{_px(o.stop)}</td>"
            f"<td class='num'>{_px(o.tp1)}<br>{_px(o.tp2)}<br>{_px(o.tp3)}</td>"
            f"<td class='num'>{o.rr:.1f}</td>"
            f"<td class='power'>{power}</td>"
            f"<td class='why'>{_h(o.evidence or o.state)}</td></tr>")
    return "".join(rows)


_TRADE_HEAD = ("<tr><th>Symbol</th><th>Dir</th><th>Tier</th><th>Prob (cal)</th>"
               "<th>Quality</th><th>Entry</th><th>Stop</th><th>Targets</th>"
               "<th>R:R</th><th>Power Line</th><th>Why</th></tr>")


def to_html(r: SessionReport, refresh_sec: int = 0) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(r.generated_ts))
    meta = f"<meta http-equiv='refresh' content='{refresh_sec}'>" if refresh_sec else ""
    parts = [f"<!doctype html><html><head><meta charset='utf-8'>{meta}"
             f"<title>IA-SR Session Report</title><style>{_CSS}</style></head><body>",
             "<h1>IA-SR · INSTITUTIONAL SESSION REPORT</h1>",
             f"<div class='sub'>{ts} · scanned {r.scanned} symbols · "
             f"{len(r.execute)} execute · {len(r.watch)} watch"
             + (f" · <span class='bad'>{len(r.errors)} errors</span>" if r.errors else "")
             + "</div>"]

    parts.append(f"<h2>Tier A — Execute ({len(r.execute)})</h2>")
    if r.execute:
        parts.append(f"<table>{_TRADE_HEAD}{_trade_rows(r.execute)}</table>")
    else:
        parts.append("<div class='empty'>No Tier-A setups — capital preserved.</div>")

    parts.append(f"<h2>Tier B — Watch ({len(r.watch)})</h2>")
    if r.watch:
        rows = "".join(
            f"<tr><td><b>{_h(o.symbol)}</b></td>"
            f"<td class='{_dir_cls(o.direction)}'>{_h(o.direction)}</td>"
            f"<td class='num'>{o.gate_score:.0f}</td><td class='num'>{o.prob:.0f}%</td>"
            f"<td>{_h(o.state)}</td>"
            f"<td class='power'>{'—' if o.power_price is None else _px(o.power_price) + ' · ' + _h(o.power_status)}</td>"
            f"<td class='why'>needs: {_h(', '.join(o.fail_reasons[:3]) or '—')}</td></tr>"
            for o in r.watch)
        parts.append("<table><tr><th>Symbol</th><th>Dir</th><th>Gate</th><th>Prob</th>"
                     "<th>State</th><th>Power Line</th><th>Missing</th></tr>" + rows + "</table>")
    else:
        parts.append("<div class='empty'>Nothing on watch.</div>")

    parts.append("<h2>Portfolio</h2>")
    expo = "".join(f"<span class='pill'>{_h(k)} {v:+d}</span>"
                   for k, v in sorted(r.exposure.items())) or "<span class='why'>flat</span>"
    parts.append(f"<div>positions <b>{r.positions}</b> · open risk <b>{r.open_risk_pct:.1f}%</b>"
                 f"<br>{expo}</div>")
    if r.rejected:
        rows = "".join(f"<tr><td>{_h(o.symbol)}</td>"
                       f"<td class='{_dir_cls(o.direction)}'>{_h(o.direction)}</td>"
                       f"<td class='bad'>{_h(why)}</td></tr>" for o, why in r.rejected)
        parts.append("<table><tr><th>Blocked</th><th>Dir</th><th>Reason</th></tr>" + rows + "</table>")

    if r.stats:
        s = r.stats
        wr = f"{s['win_rate']:.0f}%" if s["win_rate"] is not None else "—"
        ar = f"{s['avg_r']:+.2f}R" if s["avg_r"] is not None else "—"
        parts.append("<h2>Performance</h2>")
        parts.append(f"<div><span class='pill'>signals {s['total']}</span>"
                     f"<span class='pill'>open {s['open']}</span>"
                     f"<span class='pill'>resolved {s['resolved']}</span>"
                     f"<span class='pill'>win rate {wr}</span>"
                     f"<span class='pill'>avg {ar}</span></div>")
        if r.buckets and any(b.n for b in r.buckets):
            rows = "".join(f"<tr><td>{_h(b.label)}</td><td class='num'>{b.n}</td>"
                           f"<td class='num'>{b.expected:.0f}%</td>"
                           f"<td class='num'>{b.actual:.0f}%</td>"
                           f"<td class='num'>{b.gap:+.0f}%</td></tr>"
                           for b in r.buckets if b.n)
            parts.append("<table><tr><th>Bucket</th><th>N</th><th>Expected</th>"
                         "<th>Actual</th><th>Gap</th></tr>" + rows + "</table>")

    if r.parity:
        parts.append("<h2>Pine Parity (latest webhook vs this scan)</h2>")
        rows = "".join(
            f"<tr><td>{_h(p.symbol)}</td>"
            f"<td class='{'ok' if p.agree else 'bad'}'>{'AGREE' if p.agree else 'DIVERGES'}</td>"
            f"<td class='{_dir_cls(p.pine_bias)}'>{_h(p.pine_bias)} {p.pine_prob:.0f}%</td>"
            f"<td class='{_dir_cls(p.py_bias)}'>{_h(p.py_bias)} {p.py_prob:.0f}%</td>"
            f"<td class='num'>{p.age_min:.0f}m</td></tr>" for p in r.parity)
        parts.append("<table><tr><th>Symbol</th><th>Status</th><th>Pine</th>"
                     "<th>Python</th><th>Age</th></tr>" + rows + "</table>")

    if r.errors:
        parts.append("<h2>Errors</h2><div class='why'>"
                     + "<br>".join(f"{_h(k)}: {_h(v)}" for k, v in r.errors.items()) + "</div>")
    parts.append("</body></html>")
    return "".join(parts)
