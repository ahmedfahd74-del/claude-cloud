# Institutional Market Structure Engine — Research & Architecture
### "MS-Core" — deterministic, non-repainting HH/HL/LH/LL + BOS/CHoCH + MTF bias (W→D→4H→1H)
*Research first, code second. Every rule below is justified. No code until you approve.*

---

## PART 1 — WHY EVERYTHING WE TRIED LOOKED WRONG

| Method | What it does | Why it failed for us |
|---|---|---|
| **Retail zigzag (wick)** — original PMORB | new swing on every wick extreme | fires on every stop-hunt spike → false HH/LL → bias twitches. Repaints-prone. |
| **Rolling close** `ta.highest(close,N)` — my last build | "highest close in last N bars" | NOT a pivot. Slides forward, staircases, no anchor to a real turning point. This is why it "looked bad on live market." |
| **What professionals actually use** | confirmed fractal pivot: detect on wick, confirm break on close | ← this is the fix. |

**The core insight from the research (ICT / SMC / Wyckoff all agree):**
> Liquidity rests at the **wick** (that's where stops sit). A break is confirmed only by a **close**. A wick through a level that closes back inside is **not a break — it's a sweep** (a stop-hunt / Wyckoff spring).

Both our attempts broke this rule: wick-zigzag treated sweeps as breaks; rolling-close ignored the wick entirely. MS-Core respects it.

---

## PART 2 — THE RESEARCH (methods compared)

**SMC / ICT (Smart Money Concepts):** swing structure = confirmed fractal highs/lows. **BOS** (Break of Structure) = close beyond the last swing in the trend direction → *continuation*. **CHoCH** (Change of Character) = close beyond the *protected* swing against the trend → *reversal*. Bias flips **only** on CHoCH. Break is on **candle close/body**, never wick. Sources below confirm this is now the standard, with explicit "body-close BOS/CHoCH" toggles in 2025-26 tools.

**ICT liquidity / inducement:** before a real move, price sweeps **inducement** (the last minor opposite pivot) to fuel itself. A sweep *with* the HTF trend = a **run** (continuation); a sweep *against* structure that then reverses = reversal setup. "The bigger the timeframe, the more liquidity sits there" → **HTF gates LTF**.

**Wyckoff:** structure lives inside **ranges** (accumulation → markup → distribution → markdown). The **spring** (sweep below support then reclaim) and **upthrust** (sweep above then reject) are the *same event* ICT calls a liquidity sweep. Gives us the range/premium-discount framing.

**Order flow / displacement:** a break with **displacement** (a strong impulsive candle leaving a Fair Value Gap) has real intent; a break that barely closes over does not. Lets us **grade** break quality instead of treating all breaks equally.

**Convergence:** all four schools describe the same skeleton in different words. MS-Core implements the skeleton once, deterministically.

---

## PART 3 — MS-CORE: THE ENGINE (every rule justified)

### Rule 1 — Swing detection = CONFIRMED FRACTAL PIVOTS (detect on wick)
- Swing High = `ta.pivothigh(high, L, R)`; Swing Low = `ta.pivotlow(low, L, R)`.
- Detect on **wick (high/low)** — that's where the liquidity/stops are (ICT definition).
- **Non-repainting by construction:** a pivot needs `R` bars to its right to *close* before it confirms; once confirmed it never moves. `R ≥ 1` guarantees zero repaint.
- **Fixes complaint #1** — real turning points, no staircase, no per-bar slide.

### Rule 2 — Two-tier structure (SMC swing vs internal)
- **Major** pivots (larger L/R) define the **trend** → drive bias.
- **Internal** pivots (small L/R) are the noise inside a leg → used only for inducement & entries.
- Trading bias off *major* structure is what stops the bias twitching.

### Rule 3 — Track the PROTECTED swing
- Uptrend → protected level = last confirmed **HL**. Downtrend → last confirmed **LH**.
- The protected swing is the **only** level whose break changes the trend. Everything else is continuation.

### Rule 4 — BOS vs CHoCH, confirmed on CLOSE  ← THE NUMBER ONE RULE
- **BOS (continuation):** uptrend & close **> last swing high** → HH, still bullish. Downtrend & close **< last swing low** → LL, still bearish.
- **CHoCH (reversal):** uptrend & close **< protected HL** → flip **bearish**. Downtrend & close **> protected LH** → flip **bullish**.
- Break measured on **close** (`barstate.isconfirmed`), never wick.
- **Bias flips ONLY on CHoCH. BOS never flips bias.** Deterministic and stable.

### Rule 5 — SWEEP vs BREAK (Wyckoff spring / ICT stop-hunt)
- Wick beyond a swing but **close back inside** → tag **SWEEP**, do **not** update structure.
- Sweep *with* HTF trend = run (fuel). Sweep *against* structure that reverses = reversal setup.
- This is the single thing separating institutional structure from retail zigzag: a stop-hunt no longer creates a false CHoCH.

### Rule 6 — INDUCEMENT grade (optional, enriches — never gates)
- Before validating a BOS, check the last minor opposite pivot (inducement) was swept.
- BOS with inducement swept = grade **A**; without = lower grade. Feeds ICS as a *confidence* term, doesn't change determinism.

### Rule 7 — MTF BIAS CASCADE  W → D → 4H → 1H
- Run MS-Core per TF from **one deterministic dataset** (same UNIDATA principle we already proved: derive from a single HTF `request.security` with `lookahead_off`, identical on every chart TF, non-repainting).
- **HTF is the boss:** 1W = macro bias; 1D must agree for "confirmed"; 4H/1H = execution timing.
- Output example: `1W Bull · 1D Bull · 4H Bull · 1H Bear` = 3 aligned + 1H pullback = highest-quality long.
- Justified: "bigger TF = more liquidity = stronger bias"; a sweep against HTF is a run, not a reversal → HTF gates LTF.

### Rule 8 — DETERMINISM / NON-REPAINT guarantees
- Pivots confirmed (offset `R`). Breaks only on `barstate.isconfirmed`.
- `request.security` uses `lookahead_off`, or `lookahead_on` **only** on already-closed `[1]` historical values (never the live bar).
- Reuse the **DS-fingerprint hash** to prove cross-TF identity (same levels/bias on 1m and 1M).

---

## PART 4 — S/R CONFLUENCE (how MS-Core plugs into our ICS engine)

Every S/R level gains a **structure-alignment** field:
1. **Is it the current protected swing?** → top weight (this is the line that matters right now).
2. **Right side of HTF bias?** support in an uptrend / resistance in a downtrend → **confluence bonus**.
3. **Naked DOL pool (Sphinx) aligned with bias?** → magnet weight.

- **ICS gains a "structure confluence" term** so a level's score reflects whether structure agrees.
- **Decision panel** shows the bias cascade + names the *one* actionable level given the bias
  (buy support in uptrend / sell resistance in downtrend).
- Levels that **contradict** the bias are **dimmed/dashed, not deleted** — chart stays honest.

---

## PART 5 — SPHINX, ADAPTED FOR CRYPTO (what we take, what we drop)

**Take:** D/W/M liquidity pools, **naked (untested) weighting**, **sweep→reclaim→OB→FVG** delivery engine, clustering/declutter.
**Drop / de-prioritize for crypto:** ORB & premarket (equities-only); NDOG/NWOG opening gaps (crypto rarely gaps — 24/7).
**Adapt:** sessions → crypto is 24/7, so Asia/London/NY session pools are optional context, **D/W/M pools are king**; anchor the "day" to **UTC** (crypto convention) rather than NY 09:30.
**Sphinx has NO structural bias** (only price-vs-open premium/discount) — MS-Core supplies the real bias.

---

## PART 6 — TWO DECISIONS BEFORE I CODE

1. **Inducement in v1, or v2?** v1 = pure BOS/CHoCH + sweep (cleaner, faster to trust). v2 adds inducement grading. Recommend **v1 first**, add inducement after you trust the base.
2. **Delivery order:** (a) build MS-Core standalone so you validate the bias on a live crypto chart *first*, THEN (b) wire confluence into the ICS engine. Recommend **standalone first** — same test-before-merge discipline that's been working.

*No code is written until you green-light this. When you do, I build MS-Core standalone, verify it three ways locally, and hand it to you for the one real test — your paste into TradingView.*

---

### Sources
- SMC/ICT market structure — BOS/CHoCH, swing points: tradingstrategyguides.com/day-3-smc-ict-market-structure-explained
- Body-close BOS/CHoCH, non-repaint confirmed pivots: mql5.com/en/code/74575 ; tradingview SMC Market Structure (CptRedd)
- Market Structure Shift (MSS): backtrex.com/en/blog/ict-market-structure-shift-mss-guide
- ICT Dealing Range / premium-discount: thesimpleict.com/dealing-range-ict-guide
- Liquidity sweep vs run, wick-vs-close, HTF gating: luxalgo.com liquidity-sweeps ; innercircletrader.net ict-liquidity-sweep-vs-liquidity-run
- Inducement vs sweep vs stop-hunt: fxnx.com/en/blog/inducement-vs-sweep-vs-stop-hunt
