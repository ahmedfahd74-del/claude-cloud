#!/usr/bin/env python3
"""TRADE CARD validator — models the decision + risk logic in level_core_v2.pine.

The card is DISCIPLINE, not prediction. It proves the account-savers:
  * side chosen from VALUE (discount → buy support · premium → sell resistance)
  * GO requires PROVEN level (bounced before) + right side + R:R ≥ min + no dir conflict
  * stop = beyond the level by a buffer · target = opposing level · R:R = reward/risk
  * size = fixed-% account risk ÷ stop distance
  * refuses untested levels, wrong side, and bad R:R
"""
NONE=float('nan')
def isna(x): return x!=x

def trade_card(close, eq, sup, res, sup_bounces, res_bounces, atr,
               dir_verdict=0, need_proven=True, min_rr=2.0, stop_buf=0.5,
               acct=1000.0, risk_pct=1.0):
    disc = not isna(eq) and close < eq
    prem = not isna(eq) and close >= eq
    side = 1 if (disc and not isna(sup)) else -1 if (prem and not isna(res)) else 0
    entry=stop=tgt=NONE; bounces=0
    if side==1:
        entry=sup; bounces=sup_bounces; stop=entry-atr*stop_buf
        tgt = res if not isna(res) else eq
    elif side==-1:
        entry=res; bounces=res_bounces; stop=entry+atr*stop_buf
        tgt = sup if not isna(sup) else eq
    risk   = NONE if (isna(entry) or isna(stop)) else abs(entry-stop)
    reward = NONE if (isna(entry) or isna(tgt))  else abs(tgt-entry)
    rr     = NONE if (isna(risk) or risk==0 or isna(reward)) else reward/risk
    proven = bounces>=2                                   # founding + >=1 real bounce
    oppose = (side==1 and dir_verdict==-1) or (side==-1 and dir_verdict==1)
    ok_proven = (not need_proven) or proven
    ok_rr = (not isna(rr)) and rr>=min_rr
    vc = 0 if side==0 else 1 if oppose else 1 if not ok_proven else 2 if not ok_rr else 3
    verdict = {0:"NO SETUP",1:"NO-GO",2:"WAIT",3:"GO"}[vc]
    units = NONE if (isna(risk) or risk==0) else (acct*risk_pct/100.0)/risk
    return dict(side=side, entry=entry, stop=stop, tgt=tgt, rr=rr, proven=proven,
                verdict=verdict, vc=vc, units=units)

if __name__=="__main__":
    # ── CLAIM 1: discount → LONG the support; premium → SHORT the resistance ──
    lo = trade_card(close=95, eq=100, sup=90, res=110, sup_bounces=3, res_bounces=3, atr=1.0)
    assert lo['side']==1 and lo['entry']==90 and lo['tgt']==110
    hi = trade_card(close=105, eq=100, sup=90, res=110, sup_bounces=3, res_bounces=3, atr=1.0)
    assert hi['side']==-1 and hi['entry']==110 and hi['tgt']==90

    # ── CLAIM 2: stop beyond the level, target opposing level, R:R = reward/risk ──
    # long: entry 90, stop 90-0.5=89.5 → risk .5 ; reward 110-90=20 → rr 40
    assert abs(lo['stop']-89.5)<1e-9 and abs(lo['rr']-40.0)<1e-9

    # ── CLAIM 3: PROVEN gate — untested level (bounces<=1) is NO-GO when required ──
    fresh = trade_card(95,100,90,110, sup_bounces=1, res_bounces=3, atr=1.0)   # support untested
    assert fresh['proven'] is False and fresh['verdict']=="NO-GO"
    fresh_ok = trade_card(95,100,90,110, sup_bounces=1, res_bounces=3, atr=1.0, need_proven=False)
    assert fresh_ok['verdict']=="GO"                                            # gate off → allowed

    # ── CLAIM 4: R:R gate — good level but poor reward = WAIT ──
    poor = trade_card(95,100,90,96, sup_bounces=3, res_bounces=3, atr=1.0, min_rr=2.0)
    # entry90 stop89.5 risk.5 ; reward 96-90=6 rr12 -> GO. make risk large:
    poor = trade_card(95,100,90,92, sup_bounces=3, res_bounces=3, atr=6.0, min_rr=2.0)
    # stop 90-3=87 risk3; reward 92-90=2 rr .67 <2 -> WAIT
    assert poor['verdict']=="WAIT" and poor['rr']<2.0

    # ── CLAIM 5: direction conflict = NO-GO (long while true dir is DOWN) ──
    conf = trade_card(95,100,90,110, sup_bounces=3, res_bounces=3, atr=1.0, dir_verdict=-1)
    assert conf['verdict']=="NO-GO"

    # ── CLAIM 6: fixed-% position size = riskAmt / stop distance ──
    sz = trade_card(95,100,90,110, sup_bounces=3, res_bounces=3, atr=1.0, acct=1000, risk_pct=1.0)
    # riskAmt=10, stop dist=.5 → units=20
    assert abs(sz['units']-20.0)<1e-9

    # ── CLAIM 7: no level on the value side = NO SETUP (never invents a trade) ──
    ns = trade_card(95,100,sup=NONE,res=110, sup_bounces=0, res_bounces=3, atr=1.0)
    assert ns['side']==0 and ns['verdict']=="NO SETUP"

    print("TRADE CARD VALIDATED:")
    print("  value-side selection · stop/target/RR geometry · PROVEN gate · R:R gate ·")
    print("  direction-conflict gate · fixed-% sizing · never invents a setup")
    print("  all 7 claims PASS")
