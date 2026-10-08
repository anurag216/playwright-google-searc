#!/usr/bin/env python3
from __future__ import annotations

import csv, json, math, statistics, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

BASE = "https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2026_{month}.csv"
MONTHS = ["01","02","03","04","05","06","07","08"]
DEV = ["01","02","03","04","05"]
VAL = ["06","07"]
HOLD = ["08"]
BASE_COST = 0.26
STRESS_COST = 0.36
HARD_STRESS_COST = 0.46

SESSIONS = {
    "all": [(0,24)],
    "asia": [(0,6)],
    "london": [(6,12)],
    "ny_overlap": [(12,17)],
    "ny_late": [(17,22)],
    "london_ny": [(6,17)],
    "us": [(12,22)],
}

OUT = Path("research_output")
DATA = OUT / "data"
OUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup:
    fam: str
    a: float = 0
    b: float = 0
    c: float = 0
    d: float = 0
    e: float = 0
    f: float = 0

@dataclass(frozen=True)
class Exit:
    kind: str
    a: float
    b: float = 0
    c: int = 0

@dataclass
class Trade:
    entry: int
    dir: int
    entry_px: float
    atr: float
    hour: int

def dl(month, side):
    p = DATA / f"{side}_{month}.csv"
    if not p.exists():
        urllib.request.urlretrieve(BASE.format(side=side, month=month), p)
    return p

def read_side(path):
    out = {}
    with path.open() as f:
        for z in csv.DictReader(f):
            out[int(z["timestamp"])] = (
                float(z["open"]), float(z["high"]),
                float(z["low"]), float(z["close"])
            )
    return out

def rolling_extreme(arr, w, is_max=True):
    from collections import deque
    n = len(arr)
    out = [None] * n
    dq = deque()
    for i, x in enumerate(arr):
        while dq and dq[0] <= i - w:
            dq.popleft()
        while dq and ((arr[dq[-1]] <= x) if is_max else (arr[dq[-1]] >= x)):
            dq.pop()
        dq.append(i)
        if i >= w:
            # exclude current bar: rebuild front validity for [i-w, i)
            while dq and dq[0] == i:
                # current must not be part of previous-window extreme
                break
            vals = arr[i-w:i]
            out[i] = max(vals) if is_max else min(vals)
    return out

def load_month(month):
    A = read_side(dl(month, "ask"))
    B = read_side(dl(month, "bid"))
    ts = sorted(set(A) & set(B))
    bars = []
    for t in ts:
        a, b = A[t], B[t]
        bars.append({
            "t": t,
            "o": (a[0]+b[0])/2,
            "h": (a[1]+b[1])/2,
            "l": (a[2]+b[2])/2,
            "c": (a[3]+b[3])/2,
            "hour": (t // 3600000) % 24,
        })

    close = [x["c"] for x in bars]
    high = [x["h"] for x in bars]
    low = [x["l"] for x in bars]
    tr = [0.0] * len(bars)
    for i in range(1, len(bars)):
        tr[i] = max(
            high[i]-low[i],
            abs(high[i]-close[i-1]),
            abs(low[i]-close[i-1]),
        )

    atr = {}
    for w in (5,10,20,60):
        a = [0.0] * len(bars)
        s = 0.0
        for i in range(len(bars)):
            s += tr[i]
            if i >= w:
                s -= tr[i-w]
            a[i] = s / min(i+1, w)
        atr[w] = a

    # precompute rolling previous-window extrema for all windows we use
    prev = {}
    for w in (5,10,20,30,60):
        ph = [None]*len(bars)
        pl = [None]*len(bars)
        for i in range(w, len(bars)):
            ph[i] = max(high[i-w:i])
            pl[i] = min(low[i-w:i])
        prev[w] = (ph,pl)

    return {
        "bars": bars, "close": close, "high": high, "low": low,
        "tr": tr, "atr": atr, "prev": prev,
    }

def sgn(x):
    return 1 if x > 0 else -1 if x < 0 else 0

def path_eff(ctx, i, w):
    c = ctx["close"]
    path = 0.0
    for k in range(i-w+1, i+1):
        path += abs(c[k]-c[k-1])
    return abs(c[i]-c[i-w]) / (path + 1e-12)

def zscore(ctx, i, w):
    a = ctx["close"][i-w+1:i+1]
    mu = sum(a) / w
    sd = statistics.pstdev(a)
    return 0.0 if sd < 1e-12 else (ctx["close"][i]-mu)/sd

def make_setups():
    q = []

    # impulse -> pullback -> reacceleration
    for n in (5,10,20):
        for k in (1.5,2,3):
            for ef in (.5,.7):
                for pb in (.35,.5,.65):
                    for retain in (.1,.3):
                        for wait in (2,4):
                            q.append(Setup("ipr",n,k,ef,pb,retain,wait))

    # liquidity sweep / failed breakout -> reclaim
    for n in (10,20,60):
        for ov in (.15,.3,.6):
            for wick in (.45,.65,.8):
                for rec in (0,.15):
                    q.append(Setup("sweep",n,ov,wick,rec))

    # breakout -> retest -> confirmation
    for n in (10,20,60):
        for bo in (0,.2,.4):
            for band in (.2,.4):
                for inv in (.4,.8):
                    for wait in (2,4):
                        q.append(Setup("brt",n,bo,band,inv,wait))

    # compression -> range expansion
    for sw in (5,10):
        for lw in (30,60):
            for cr in (.25,.4,.55):
                for ex in (1.0,1.5,2.0):
                    q.append(Setup("compress",sw,lw,cr,ex))

    # stretched mean-reversion with immediate turn
    for w in (20,30,60):
        for z in (1.5,2,2.5,3):
            for me in (.25,.4,.55):
                q.append(Setup("mr",w,z,me))

    # established trend -> short pullback -> resume
    for w in (20,30,60):
        for k in (1.5,2,3,4):
            for ef in (.35,.5,.65):
                for pbn in (1,2,3):
                    q.append(Setup("trend",w,k,ef,pbn))

    return q

def gen_signals(ctx, setup):
    b = ctx["bars"]
    c = ctx["close"]
    hi = ctx["high"]
    lo = ctx["low"]
    atr = ctx["atr"]
    prev = ctx["prev"]
    N = len(b)
    out = []

    if setup.fam == "ipr":
        w,k,me,pb,retain,wait = int(setup.a),setup.b,setup.c,setup.d,setup.e,int(setup.f)
        for i in range(max(65,w+2),N-10):
            mv = c[i]-c[i-w]
            d = sgn(mv)
            a = max(atr[20][i], .05)
            if not d or abs(mv) < k*a or path_eff(ctx,i,w) < me:
                continue
            base, peak = c[i-w], c[i]
            retr = -1
            for j in range(i+1, min(N-2, i+wait+1)):
                if d*(peak-c[j]) >= pb*abs(mv) and d*(c[j]-base) >= retain*abs(mv):
                    retr = j
                    break
            if retr < 0:
                continue
            j = retr + 1
            if j < N-1 and sgn(c[j]-c[j-1]) == d and d*(c[j]-base) >= retain*abs(mv):
                out.append(Trade(j+1,d,b[j+1]["o"],atr[20][j],b[j+1]["hour"]))

    elif setup.fam == "sweep":
        w,ov,wick,rec = int(setup.a),setup.b,setup.c,setup.d
        ph,pl = prev[w]
        for i in range(max(65,w),N-2):
            if ph[i] is None:
                continue
            a = max(atr[20][i], .05)
            rng = hi[i]-lo[i]
            if rng <= 0:
                continue
            if hi[i]-ph[i] >= ov*a and c[i] <= ph[i]-rec*a and (hi[i]-c[i])/rng >= wick:
                out.append(Trade(i+1,-1,b[i+1]["o"],a,b[i+1]["hour"]))
            elif pl[i]-lo[i] >= ov*a and c[i] >= pl[i]+rec*a and (c[i]-lo[i])/rng >= wick:
                out.append(Trade(i+1,1,b[i+1]["o"],a,b[i+1]["hour"]))

    elif setup.fam == "brt":
        w,bo,band,inv,wait = int(setup.a),setup.b,setup.c,setup.d,int(setup.e)
        ph,pl = prev[w]
        for i in range(max(65,w),N-10):
            a = max(atr[20][i], .05)
            d, level = 0, 0.0
            if c[i] >= ph[i] + bo*a:
                d, level = 1, ph[i]
            elif c[i] <= pl[i] - bo*a:
                d, level = -1, pl[i]
            else:
                continue
            ret = -1
            for j in range(i+1, min(N-2, i+wait+1)):
                if d == 1 and lo[j] <= level+band*a and c[j] >= level-inv*a:
                    ret = j
                    break
                if d == -1 and hi[j] >= level-band*a and c[j] <= level+inv*a:
                    ret = j
                    break
            if ret < 0:
                continue
            if d == 1 and c[ret] > level and c[ret] > b[ret]["o"]:
                out.append(Trade(ret+1,d,b[ret+1]["o"],a,b[ret+1]["hour"]))
            elif d == -1 and c[ret] < level and c[ret] < b[ret]["o"]:
                out.append(Trade(ret+1,d,b[ret+1]["o"],a,b[ret+1]["hour"]))

    elif setup.fam == "compress":
        sw,lw,cr,ex = int(setup.a),int(setup.b),setup.c,setup.d
        ph,pl = prev[sw]
        for i in range(max(65,lw),N-2):
            short_range = max(hi[i-sw:i]) - min(lo[i-sw:i])
            long_range = max(hi[i-lw:i]) - min(lo[i-lw:i])
            a = max(atr[20][i], .05)
            if long_range <= 0 or short_range/long_range > cr or hi[i]-lo[i] < ex*a:
                continue
            if c[i] > ph[i]:
                out.append(Trade(i+1,1,b[i+1]["o"],a,b[i+1]["hour"]))
            elif c[i] < pl[i]:
                out.append(Trade(i+1,-1,b[i+1]["o"],a,b[i+1]["hour"]))

    elif setup.fam == "mr":
        w,zt,me = int(setup.a),setup.b,setup.c
        for i in range(max(65,w),N-2):
            z = zscore(ctx,i,w)
            d = -sgn(z)
            if not d or abs(z) < zt or path_eff(ctx,i,min(20,w)) > me:
                continue
            if sgn(c[i]-c[i-1]) == d:
                out.append(Trade(i+1,d,b[i+1]["o"],atr[20][i],b[i+1]["hour"]))

    elif setup.fam == "trend":
        w,k,me,pbn = int(setup.a),setup.b,setup.c,int(setup.d)
        for i in range(max(65,w+pbn),N-2):
            mv = c[i]-c[i-w]
            d = sgn(mv)
            a = max(atr[20][i], .05)
            if not d or abs(mv) < k*a or path_eff(ctx,i,w) < me:
                continue
            if not all(d*(c[j]-c[j-1]) <= 0 for j in range(i-pbn,i)):
                continue
            if d*(c[i]-c[i-1]) > 0:
                out.append(Trade(i+1,d,b[i+1]["o"],a,b[i+1]["hour"]))

    return out

def make_exits():
    q = [Exit("hold",h) for h in (3,5,10,15,20,30)]
    for tp in (.75,1.0,1.5,2.0):
        for sl in (.75,1.0,1.25,1.5):
            for mh in (5,10,20):
                q.append(Exit("bracket",tp,sl,mh))
    return q

def in_session(hour, name):
    return any(a <= hour < b for a,b in SESSIONS[name])

def simulate_month(ctx, trades, ex, session, direction, cost):
    b = ctx["bars"]
    pnls = []
    busy = -1

    for t in trades:
        if t.entry <= busy:
            continue
        if not in_session(t.hour, session):
            continue
        if direction and t.dir != direction:
            continue

        ep, d = t.entry_px, t.dir
        if ex.kind == "hold":
            end = t.entry + int(ex.a)
            if end >= len(b):
                break
            gross = d * (b[end]["o"] - ep)
            busy = end
        else:
            tp = max(.05, ex.a*t.atr)
            sl = max(.05, ex.b*t.atr)
            last = min(len(b)-1, t.entry+ex.c)
            gross = None
            end = last

            for j in range(t.entry, last+1):
                hit_tp = (b[j]["h"] >= ep+tp) if d == 1 else (b[j]["l"] <= ep-tp)
                hit_sl = (b[j]["l"] <= ep-sl) if d == 1 else (b[j]["h"] >= ep+sl)

                # conservative ambiguity handling: if both touched in same M1 bar, SL wins.
                if hit_tp and hit_sl:
                    gross, end = -sl, j
                    break
                if hit_sl:
                    gross, end = -sl, j
                    break
                if hit_tp:
                    gross, end = tp, j
                    break

            if gross is None:
                gross = d * (b[last]["c"] - ep)
            busy = end

        pnls.append(gross - cost)

    return pnls

def stats(p):
    if not p:
        return {"n":0,"sum":0,"mean":0,"pf":0,"win":0,"mdd":0}
    gp = sum(x for x in p if x > 0)
    gl = -sum(x for x in p if x <= 0)
    eq = peak = mdd = 0.0
    for x in p:
        eq += x
        peak = max(peak, eq)
        mdd = max(mdd, peak-eq)
    return {
        "n": len(p),
        "sum": sum(p),
        "mean": sum(p)/len(p),
        "pf": gp/gl if gl > 0 else 99,
        "win": sum(x > 0 for x in p)/len(p),
        "mdd": mdd,
    }

def aggregate(months, ctxs, sigs, ex, session, direction, cost):
    allp = []
    monthly = {}
    for m in months:
        p = simulate_month(ctxs[m], sigs[m], ex, session, direction, cost)
        monthly[m] = stats(p)
        allp.extend(p)
    return stats(allp), monthly

def robust_score(st, monthly, stress, required_positive_months):
    pos = sum(monthly[m]["sum"] > 0 for m in monthly)
    if (
        st["n"] < 50 or st["sum"] <= 0 or st["pf"] <= 1.02 or
        stress["sum"] <= 0 or pos < required_positive_months
    ):
        return None
    med = statistics.median(monthly[m]["mean"] for m in monthly)
    return (
        (min(st["pf"],2.0)-1.0)
        * math.sqrt(st["n"])
        * max(st["mean"],0.001)
        * (1.0 + pos/len(monthly))
        / (1.0 + st["mdd"]/max(st["sum"],1.0))
        + max(med,0.0)
    )

def main():
    print("Loading Jan-Aug 2026 XAUUSD...")
    ctxs = {m: load_month(m) for m in MONTHS}
    print("rows", {m:len(ctxs[m]["bars"]) for m in MONTHS})

    setups = make_setups()
    print("setup_count", len(setups))

    # Generate signals only once per setup/month.
    all_sigs = {}
    for i,s in enumerate(setups):
        all_sigs[i] = {m:gen_signals(ctxs[m],s) for m in MONTHS}
        if (i+1) % 100 == 0:
            print("signals_generated", i+1)

    # -------------------- STAGE 1: cheap signal screening --------------------
    coarse_sessions = ["all","london_ny","us"]
    coarse_holds = [3,5,10,20]
    coarse_dirs = [0,1,-1]
    stage1 = []

    for idx,s in enumerate(setups):
        sigs = all_sigs[idx]
        for sess in coarse_sessions:
            for direc in coarse_dirs:
                for h in coarse_holds:
                    ex = Exit("hold",h)
                    st,mon = aggregate(DEV,ctxs,sigs,ex,sess,direc,BASE_COST)
                    stress,_ = aggregate(DEV,ctxs,sigs,ex,sess,direc,STRESS_COST)
                    sc = robust_score(st,mon,stress,3)
                    if sc is not None:
                        stage1.append((sc,idx,sess,direc,h,st,mon,stress))

    stage1.sort(reverse=True,key=lambda x:x[0])
    shortlist = stage1[:60]
    shortlisted_setup_ids = sorted(set(x[1] for x in shortlist))
    print("stage1_viable",len(stage1),"stage1_shortlist",len(shortlist),"unique_setups",len(shortlisted_setup_ids))

    # -------------------- STAGE 2: expensive exit/session search -------------
    exits = make_exits()
    stage2 = []

    for idx in shortlisted_setup_ids:
        sigs = all_sigs[idx]
        for ex in exits:
            for sess in SESSIONS:
                for direc in (0,1,-1):
                    st,mon = aggregate(DEV,ctxs,sigs,ex,sess,direc,BASE_COST)
                    stress,_ = aggregate(DEV,ctxs,sigs,ex,sess,direc,STRESS_COST)
                    sc = robust_score(st,mon,stress,3)
                    if sc is not None:
                        stage2.append((sc,idx,ex,sess,direc,st,mon,stress))

    stage2.sort(reverse=True,key=lambda x:x[0])
    dev_top = stage2[:180]
    print("stage2_viable",len(stage2),"dev_top",len(dev_top))

    # -------------------- VALIDATION: Jun-Jul --------------------------------
    validated = []
    for row in dev_top:
        sc,idx,ex,sess,direc,dst,dmon,dstress = row
        vst,vmon = aggregate(VAL,ctxs,all_sigs[idx],ex,sess,direc,BASE_COST)
        vstress,_ = aggregate(VAL,ctxs,all_sigs[idx],ex,sess,direc,STRESS_COST)

        # Require positive combined validation and both months individually positive.
        if (
            vst["n"] >= 18 and vst["sum"] > 0 and vst["pf"] > 1.03 and
            vstress["sum"] >= 0 and
            all(vmon[m]["sum"] > 0 for m in VAL)
        ):
            vscore = (
                (vst["pf"]-1.0) * math.sqrt(vst["n"]) * max(vst["mean"],0.001)
                / (1.0 + vst["mdd"]/max(vst["sum"],1.0))
            )
            validated.append((vscore,row,vst,vmon,vstress))

    validated.sort(reverse=True,key=lambda x:x[0])
    frozen = validated[:30]
    print("validation_viable",len(validated),"frozen_for_august",len(frozen))

    # -------------------- HOLDOUT: August, viewed once ------------------------
    final = []
    for vscore,row,vst,vmon,vstress in frozen:
        sc,idx,ex,sess,direc,dst,dmon,dstress = row
        hst,hmon = aggregate(HOLD,ctxs,all_sigs[idx],ex,sess,direc,BASE_COST)
        h36,_ = aggregate(HOLD,ctxs,all_sigs[idx],ex,sess,direc,STRESS_COST)
        h46,_ = aggregate(HOLD,ctxs,all_sigs[idx],ex,sess,direc,HARD_STRESS_COST)

        final.append({
            "setup": asdict(setups[idx]),
            "exit": asdict(ex),
            "session": sess,
            "direction": direc,
            "development": dst,
            "development_monthly": dmon,
            "development_cost36": dstress,
            "validation": vst,
            "validation_monthly": vmon,
            "validation_cost36": vstress,
            "holdout": hst,
            "holdout_cost36": h36,
            "holdout_cost46": h46,
        })

    survivors = [
        r for r in final
        if (
            r["holdout"]["n"] >= 8 and
            r["holdout"]["sum"] > 0 and
            r["holdout"]["pf"] > 1.05 and
            r["holdout_cost36"]["sum"] >= 0
        )
    ]
    survivors.sort(
        key=lambda r: (
            r["holdout_cost36"]["sum"] > 0,
            r["holdout"]["pf"],
            r["holdout"]["mean"],
        ),
        reverse=True,
    )

    payload = {
        "method": {
            "development": "2026-01 through 2026-05",
            "validation": "2026-06 through 2026-07",
            "holdout": "2026-08",
            "base_roundtrip_cost": BASE_COST,
            "stress_roundtrip_cost": STRESS_COST,
            "hard_stress_roundtrip_cost": HARD_STRESS_COST,
            "one_position_at_a_time": True,
            "same_bar_tp_sl_policy": "SL first (conservative)",
            "selection_rule": "August never used before frozen shortlist",
        },
        "counts": {
            "setups": len(setups),
            "stage1_viable": len(stage1),
            "stage1_shortlist": len(shortlist),
            "stage2_viable": len(stage2),
            "validation_viable": len(validated),
            "frozen": len(frozen),
            "holdout_survivors": len(survivors),
        },
        "survivors": survivors,
        "frozen_candidates": final,
    }

    (OUT/"walkforward_results.json").write_text(json.dumps(payload,indent=2))

    with (OUT/"walkforward_summary.md").open("w") as f:
        f.write("# XAUUSD staged walk-forward research\n\n")
        f.write("Heavy search is staged to avoid brute-force runtime and overfitting.\n\n")
        for k,v in payload["method"].items():
            f.write(f"- **{k}**: {v}\n")
        f.write("\n## Counts\n\n")
        for k,v in payload["counts"].items():
            f.write(f"- {k}: {v}\n")
        f.write("\n## Holdout survivors\n\n")
        if not survivors:
            f.write("No candidate passed the frozen August holdout gate.\n")
        for i,r in enumerate(survivors[:15],1):
            f.write(f"### Survivor {i}\n")
            f.write(f"- setup: `{r['setup']}`\n")
            f.write(f"- exit: `{r['exit']}`\n")
            f.write(f"- session: {r['session']}\n")
            f.write(f"- direction: {r['direction']}\n")
            for key in ("development","validation","holdout","holdout_cost36","holdout_cost46"):
                f.write(f"- {key}: `{r[key]}`\n")
            f.write("\n")

    compact = {
        "counts": payload["counts"],
        "top_survivors": survivors[:5],
        "top_frozen_if_none": final[:5] if not survivors else [],
    }
    print(json.dumps(compact, indent=2))

if __name__ == "__main__":
    main()
