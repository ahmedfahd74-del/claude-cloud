# Two-Layer Institutional Platform — Architecture & Migration Plan

Pine = execution terminal. Python = master intelligence. One logic model, two runtimes.

---

## 0. Honest comms reality (drives the whole design)

| Direction | Feasible? | Mechanism |
|---|---|---|
| Pine → Python | **Yes, automated** | `alert()` webhook on bar close (Section 16 JSON export) |
| Python → Pine, automated data push | **No** | TradingView indicators have no inbound API; `request.security()` reads TV symbols only |
| Python → Pine, human-in-the-loop | **Yes** | Python ranks the market → human opens the top-ranked symbol's chart → Pine's full engine produces the trade plan |
| Python → broker | Out of scope | This project is decision support; paper-trading-only is a platform invariant |

**Design consequence.** Python is the scanner and ranker; Pine is authoritative for whatever chart is open. The "handoff" from Python to Pine is a human opening the chart Python ranked #1. No architecture that pretends otherwise is honest, and Section 15 of the Pine script already states this on-chart.

---

## 1. Module classification

| Module | Pine section | Final home | Why |
|---|---|---|---|
| Adaptive Regime Engine | 3–4 | **Shared spec** (both runtimes) | Pure, unitless math; cheap in both languages |
| Swing Engine | 5 | **Shared spec** | Fixed-cost detector; direct port |
| HTF Fetch | 6 | **Pine only** (Python uses its own data feed) | `request.security()` is TV-specific; Python fetches OHLCV itself |
| Level Store + auto-clean | 7 | **Shared spec** | Stateful book; Python version drops the drawing arrays |
| Liquidity / SMC (FVG, OB, sweeps, EQH/EQL) | 8 | **Shared spec** | Confirmed-bar detectors; direct port |
| Scoring + Confluence | 9 | **Shared spec** — Python becomes master | Weights `W_*` are the tunable surface the Learning Engine will recalibrate |
| Decision Engine / Market State | 10 | **Shared spec** — Python becomes master | Priority-ordered classifier; trivially portable |
| Probability + Trade Quality | 11 | **Shared spec** — Python becomes master | Signed-evidence model; Python replaces static weights with learned ones |
| Performance / Self-Review | 12 | **Python master**, Pine keeps its lightweight local view | Real learning needs persistent storage Pine doesn't have |
| Dashboard | 13 | **Pine only** | Visualization is Pine's job |
| Trade Execution Engine (plan: entry/SL/TP/R:R) | 14 | **Pine only** | Chart-native; consumes the level book + validation gate |
| Setup Scanner | 15 | **Python only** (Pine stub stays honest) | The Pine limitation that motivated this architecture |
| Data Export | 16 | **Pine only** | The bridge itself |
| Global Market Scanner | — | **Python only** | Hundreds of symbols; impossible in Pine |
| Opportunity Ranking | — | **Python only** | Cross-symbol comparison |
| Portfolio Intelligence (correlation, exposure) | — | **Python only** | Needs multi-position state |
| Learning Engine (outcome DB, calibration) | — | **Python only** | Needs a database |
| AI Explanation Engine | — | **Python only** (Pine's Evidence row is the seed) | Section 13's evidence string is already the per-factor format |

"Shared spec" means: one written specification of the algorithm (this repo), two implementations that must pass parity tests against each other. Pine's implementation is never weakened; Python's is a faithful port.

---

## 2. Single source of truth

Section 16's JSON payload is the **only sanctioned snapshot** of the engine's decision state:

```json
{"v":1, "sym":"EURUSD", "tf":"60", "state":"Momentum Continuation",
 "bias":"LONG", "bull":84, "bear":16, "quality":"High Quality",
 "htfAlign":2, "supConf":78, "resConf":41}
```

Rules:
1. No downstream consumer recomputes `bias`/`bull`/`quality` for the chart context — they read the export. Python computes them only for symbols/timeframes Pine isn't watching.
2. The schema is **versioned** (`v`) and **additive-only**: new fields may be appended; existing fields never change meaning. A `v` bump signals a breaking change.
3. One emission per confirmed bar (`alert.freq_once_per_bar_close`) — no intrabar noise, no repaint in the data trail.
4. When Pine and Python disagree on a chart Pine is open on, **Pine wins for that chart** and the disagreement is logged as a calibration bug in Python.

---

## 3. Migration roadmap

- **Phase A — Freeze & bridge (done).** Pine feature set frozen; Section 15 scanner made honest; Section 16 JSON export added with schema version.
- **Phase B — Ingest.** Python webhook receiver stores every payload (symbol, tf, timestamp, full JSON). No intelligence yet — just an audit trail that doubles as the parity dataset.
- **Phase C — Port the shared spec.** Implement regime → swings → level book → SMC → scoring → decision → probability in Python against raw OHLCV. **Parity gate:** replaying the same bars must reproduce Pine's exported `state`/`bias`/`bull` within tolerance before anything downstream is built.
- **Phase D — Scale out.** Global scanner (FX, crypto, indices, commodities; stocks later) across 1M→1W, HTF-alignment model, opportunity ranking table, per-factor explanation output.
- **Phase E — Close the loop.** Portfolio intelligence (correlation/exposure caps) and the Learning Engine: store outcomes, measure probability calibration (Pine's `calibGap` is the prototype), recalibrate the `W_*` weights. Updated weights flow back to Pine as documented input presets — a manual, versioned sync, because that's the only honest channel.
- **Phase F — Optional execution.** Paper-execution integration in Python (this monorepo's `PaperExecutionService` is the natural home). Live execution stays out of scope.

Repo note: the Python layer belongs in this monorepo — `services/` already reserves the slots, and the FastAPI pipeline (Scan → Challenge → Rank → Allocate → Paper Execute) is the same shape Phase D produces.

---

## 4. Pine refactors done for the transition (nothing weakened)

- **Section 16 export** — the bridge, versioned payload, confirmed bars only.
- **Section 15 honesty** — the scanner reports the real chart verdict and explicitly marks foreign symbols/TFs unsupported instead of faking them.
- **Named weight constants (`W_TOUCH`…`W_SMC`, Section 9)** and the signed-evidence table (Section 11) — the exact surfaces the Learning Engine will retune; they are constants, not scattered literals.
- **Deliberately not done:** splitting logic out of Pine, dual-maintenance stubs, or any thinning of the chart engine. Pine remains fully authoritative for the open chart.

## 5. Performance posture (already institutional-grade)

7 bundled `request.security()` calls (one per TF, tuple-packed); fixed-bound swing loop (`2×MAXLEG`) so cost is constant; capped, self-pruning arrays everywhere (levels per TF, FVGs ≤ 30, prediction windows); panels and trade plan drawn only on `barstate.islast`; SMC zones score-only by default (no boxes). Keep this posture: any new Pine feature must justify its object count and per-bar loop cost.
