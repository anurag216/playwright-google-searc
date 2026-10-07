#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2026_{month}.csv'
MONTHS=['01','02','03','04','05','06','07','08']
DEV=set(['01','02','03','04','05']); VAL=set(['06','07']); HOLD=set(['08'])
SESSIONS={
 'all':[(0,24)], 'asia':[(0,6)], 'london':[(6,12)], 'ny_overlap':[(12,17)],
 'ny_late':[(17,22)], 'london_ny':[(6,17)], 'us':[(12,22)]
}
OUT=Path('research_output'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup:
    fam:str; a:float=0; b:float=0; c:float=0; d:float=0; e:float=0; f:float=0
@dataclass(frozen=True)
class Exit:
    kind:str; a:float; b:float=0; c:int=0
@dataclass
class Trade:
    month:str; entry:int; dir:int; entry_px:float; atr:float; hour:int

def dl(month,side):
    p=DATA/f'{side}_{month}.csv'
    if not p.exists(): urllib.request.urlretrieve(BASE.format(side=side,month=month),p)
    return p

def read_side(p):
    out={}
    with p.open() as f:
        r=csv.DictReader(f)
        for z in r:
            t=int(z['timestamp']); out[t]=(float(z['open']),float(z['high']),float(z['low']),float(z['close']))
    return out

def load_month(m):
    A=read_side(dl(m,'ask')); B=read_side(dl(m,'bid')); ts=sorted(set(A)&set(B)); bars=[]
    for t in ts:
        a=A[t]; b=B[t]
        bars.append({'t':t,'o':(a[0]+b[0])/2,'h':(a[1]+b[1])/2,'l':(a[2]+b[2])/2,'c':(a[3]+b[3])/2,'hour':(t//3600000)%24})
    return bars

def sgn(x): return 1 if x>0 else -1 if x<0 else 0

def prep(b):
    n=len(b); close=[x['c'] for x in b]; hi=[x['h'] for x in b]; lo=[x['l'] for x in b]
    tr=[0.0]*n
    for i in range(1,n): tr[i]=max(hi[i]-lo[i],abs(hi[i]-close[i-1]),abs(lo[i]-close[i-1]))
    atr={w:[0.0]*n for w in (5,10,20,60)}
    for w in atr:
        s=0.0
        for i in range(n):
            s+=tr[i]
            if i>=w:s-=tr[i-w]
            atr[w][i]=s/min(i+1,w)
    return close,hi,lo,tr,atr

def eff(close,i,w):
    path=sum(abs(close[k]-close[k-1]) for k in range(i-w+1,i+1))
    return abs(close[i]-close[i-w])/(path+1e-12)

def rolling_ext(hi,lo,i,w): return max(hi[i-w:i]),min(lo[i-w:i])

def zscore(close,i,w):
    a=close[i-w+1:i+1]; mu=sum(a)/w; sd=statistics.pstdev(a)
    return 0 if sd<1e-12 else (close[i]-mu)/sd

def make_setups():
    q=[]
    for n in (5,10,20,30):
      for k in (1.5,2,2.5,3):
       for ef in (.45,.6,.75):
        for pb in (.35,.5,.65):
         for ret in (.1,.3,.5):
          for wait in (2,4,6): q.append(Setup('ipr',n,k,ef,pb,ret,wait))
    for n in (10,20,60):
     for ov in (.15,.3,.5,.8):
      for wick in (.4,.6,.75):
       for rec in (0,.1,.25): q.append(Setup('sweep',n,ov,wick,rec))
    for n in (10,20,60):
     for bo in (0,.15,.3,.5):
      for band in (.15,.3,.5):
       for inv in (.3,.6,1.0):
        for wait in (2,4,6): q.append(Setup('brt',n,bo,band,inv,wait))
    for s in (5,10):
     for l in (30,60):
      for cr in (.25,.4,.55):
       for ex in (1.0,1.5,2.0): q.append(Setup('compress',s,l,cr,ex))
    for w in (20,60):
     for z in (1.5,2,2.5,3):
      for me in (.25,.4,.55): q.append(Setup('mr',w,z,me))
    for w in (20,30,60):
     for k in (1.5,2,3,4):
      for ef in (.35,.5,.65):
       for pb in (1,2,3): q.append(Setup('trend',w,k,ef,pb))
    return q

def gen_signals(m,b,setup):
    close,hi,lo,tr,atr=prep(b); out=[]; N=len(b)
    if setup.fam=='ipr':
        w,k,me,pb,retain,wait=int(setup.a),setup.b,setup.c,setup.d,setup.e,int(setup.f)
        for i in range(max(65,w+2),N-10):
            mv=close[i]-close[i-w]; d=sgn(mv); a=max(atr[20][i],.05)
            if not d or abs(mv)<k*a or eff(close,i,w)<me: continue
            base=close[i-w]; peak=close[i]; retr=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if d*(peak-close[j])>=pb*abs(mv) and d*(close[j]-base)>=retain*abs(mv):
                    retr=j; break
            if retr<0: continue
            j=retr+1
            if j<N-1 and sgn(close[j]-close[j-1])==d and d*(close[j]-base)>=retain*abs(mv):
                out.append(Trade(m,j+1,d,b[j+1]['o'],atr[20][j],b[j+1]['hour']))
    elif setup.fam=='sweep':
        w,ov,wick,rec=int(setup.a),setup.b,setup.c,setup.d
        for i in range(max(65,w),N-2):
            ph,pl=rolling_ext(hi,lo,i,w); a=max(atr[20][i],.05); rng=hi[i]-lo[i]
            if rng<=0: continue
            if hi[i]-ph>=ov*a and close[i]<=ph-rec*a and (hi[i]-close[i])/rng>=wick:
                out.append(Trade(m,i+1,-1,b[i+1]['o'],a,b[i+1]['hour']))
            elif pl-lo[i]>=ov*a and close[i]>=pl+rec*a and (close[i]-lo[i])/rng>=wick:
                out.append(Trade(m,i+1,1,b[i+1]['o'],a,b[i+1]['hour']))
    elif setup.fam=='brt':
        w,bo,band,inv,wait=int(setup.a),setup.b,setup.c,setup.d,int(setup.e)
        for i in range(max(65,w),N-10):
            ph,pl=rolling_ext(hi,lo,i,w); a=max(atr[20][i],.05); d=0; level=0
            if close[i]>=ph+bo*a: d=1;level=ph
            elif close[i]<=pl-bo*a: d=-1;level=pl
            else: continue
            ret=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if d==1 and lo[j]<=level+band*a and close[j]>=level-inv*a: ret=j;break
                if d==-1 and hi[j]>=level-band*a and close[j]<=level+inv*a: ret=j;break
            if ret<0: continue
            j=ret
            if d==1 and close[j]>level and close[j]>b[j]['o']:
                out.append(Trade(m,j+1,d,b[j+1]['o'],a,b[j+1]['hour']))
            elif d==-1 and close[j]<level and close[j]<b[j]['o']:
                out.append(Trade(m,j+1,d,b[j+1]['o'],a,b[j+1]['hour']))
    elif setup.fam=='compress':
        sw,lw,cr,ex=int(setup.a),int(setup.b),setup.c,setup.d
        for i in range(max(65,lw),N-2):
            sh=max(hi[i-sw:i])-min(lo[i-sw:i]); lh=max(hi[i-lw:i])-min(lo[i-lw:i]); a=max(atr[20][i],.05)
            if lh<=0 or sh/lh>cr or hi[i]-lo[i]<ex*a: continue
            ph,pl=rolling_ext(hi,lo,i,sw)
            if close[i]>ph: out.append(Trade(m,i+1,1,b[i+1]['o'],a,b[i+1]['hour']))
            elif close[i]<pl: out.append(Trade(m,i+1,-1,b[i+1]['o'],a,b[i+1]['hour']))
    elif setup.fam=='mr':
        w,zt,me=int(setup.a),setup.b,setup.c
        for i in range(max(65,w),N-2):
            z=zscore(close,i,w); d=-sgn(z)
            if not d or abs(z)<zt or eff(close,i,min(20,w))>me: continue
            if sgn(close[i]-close[i-1])==d:
                out.append(Trade(m,i+1,d,b[i+1]['o'],atr[20][i],b[i+1]['hour']))
    elif setup.fam=='trend':
        w,k,me,pbn=int(setup.a),setup.b,setup.c,int(setup.d)
        for i in range(max(65,w+pbn),N-2):
            mv=close[i]-close[i-w]; d=sgn(mv); a=max(atr[20][i],.05)
            if not d or abs(mv)<k*a or eff(close,i,w)<me: continue
            if not all(d*(close[j]-close[j-1])<=0 for j in range(i-pbn,i)): continue
            if d*(close[i]-close[i-1])>0:
                out.append(Trade(m,i+1,d,b[i+1]['o'],a,b[i+1]['hour']))
    return out

def make_exits():
    x=[Exit('hold',h) for h in (3,5,10,15,20,30)]
    for tp in (.75,1,1.25,1.5,2,2.5):
     for sl in (.5,.75,1,1.25,1.5):
      for mh in (5,10,20,30): x.append(Exit('bracket',tp,sl,mh))
    return x

def in_session(hour,name): return any(a<=hour<b for a,b in SESSIONS[name])

def simulate_month(b,trades,ex,session,direction,cost):
    pnls=[]; busy=-1
    for t in trades:
        if t.entry<=busy or not in_session(t.hour,session) or (direction and t.dir!=direction): continue
        if t.entry>=len(b)-2: continue
        ep=t.entry_px; d=t.dir
        if ex.kind=='hold':
            end=t.entry+int(ex.a)
            if end>=len(b): break
            gross=d*(b[end]['o']-ep); busy=end
        else:
            tp=max(.05,ex.a*t.atr); sl=max(.05,ex.b*t.atr); last=min(len(b)-1,t.entry+ex.c); gross=None; end=last
            for j in range(t.entry,last+1):
                hit_tp=(b[j]['h']>=ep+tp if d==1 else b[j]['l']<=ep-tp)
                hit_sl=(b[j]['l']<=ep-sl if d==1 else b[j]['h']>=ep+sl)
                if hit_tp and hit_sl: gross=-sl;end=j;break
                if hit_sl: gross=-sl;end=j;break
                if hit_tp: gross=tp;end=j;break
            if gross is None: gross=d*(b[last]['c']-ep)
            busy=end
        pnls.append(gross-cost)
    return pnls

def stats(p):
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0); gl=-sum(x for x in p if x<=0); eq=0;pk=0;dd=0
    for x in p: eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl>0 else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def aggregate(months,bars,sigs,ex,session,direction,cost):
    P=[]; monthly={}
    for m in months:
        p=simulate_month(bars[m],sigs[m],ex,session,direction,cost)
        monthly[m]=stats(p); P.extend(p)
    return stats(P),monthly

def score_dev(st,monthly,stress):
    pos=sum(monthly[m]['sum']>0 for m in monthly)
    med=statistics.median([monthly[m]['mean'] for m in monthly])
    if st['n']<60 or st['mean']<=0 or st['pf']<=1.02 or pos<3 or stress['sum']<=0:return None
    return (min(st['pf'],2)-1)*math.sqrt(st['n'])*max(st['mean'],0.001)*(1+pos/5)/(1+st['mdd']/max(abs(st['sum']),1)) + max(med,0)

def main():
    print('Loading Jan-Aug 2026 bid/ask M1...')
    bars={m:load_month(m) for m in MONTHS}; print({m:len(v) for m,v in bars.items()})
    setups=make_setups(); exits=make_exits(); print('setups',len(setups),'exits',len(exits))
    sigs={}
    for idx,s in enumerate(setups):
        sigs[idx]={m:gen_signals(m,bars[m],s) for m in MONTHS}
        if (idx+1)%200==0: print('signals',idx+1)
    dirs=[0,1,-1]; sessions=list(SESSIONS); dev=[]
    for idx,s in enumerate(setups):
      for ex in exits:
       for sess in sessions:
        for direc in dirs:
          st,mon=aggregate(DEV,bars,sigs[idx],ex,sess,direc,.26)
          st36,_=aggregate(DEV,bars,sigs[idx],ex,sess,direc,.36)
          sc=score_dev(st,mon,st36)
          if sc is not None: dev.append((sc,idx,ex,sess,direc,st,mon,st36))
    dev.sort(reverse=True,key=lambda x:x[0]); topdev=dev[:250]
    print('dev viable',len(dev),'top kept',len(topdev))
    val=[]
    for row in topdev:
        sc,idx,ex,sess,direc,dst,dmon,d36=row
        vst,vmon=aggregate(VAL,bars,sigs[idx],ex,sess,direc,.26)
        v36,_=aggregate(VAL,bars,sigs[idx],ex,sess,direc,.36)
        if vst['n']>=20 and vst['sum']>0 and vst['pf']>1.03 and v36['sum']>=0:
            vscore=(vst['pf']-1)*math.sqrt(vst['n'])*vst['mean']/(1+vst['mdd']/max(vst['sum'],1))
            val.append((vscore,row,vst,vmon,v36))
    val.sort(reverse=True,key=lambda x:x[0]); frozen=val[:30]
    print('validation viable',len(val),'frozen',len(frozen))
    results=[]
    for vscore,row,vst,vmon,v36 in frozen:
        sc,idx,ex,sess,direc,dst,dmon,d36=row
        hst,hmon=aggregate(HOLD,bars,sigs[idx],ex,sess,direc,.26)
        h36,_=aggregate(HOLD,bars,sigs[idx],ex,sess,direc,.36)
        h46,_=aggregate(HOLD,bars,sigs[idx],ex,sess,direc,.46)
        results.append({'setup':asdict(setups[idx]),'exit':asdict(ex),'session':sess,'direction':direc,'dev':dst,'dev_monthly':dmon,'dev_cost36':d36,'val':vst,'val_monthly':vmon,'val_cost36':v36,'hold':hst,'hold_cost36':h36,'hold_cost46':h46})
    survivors=[r for r in results if r['hold']['n']>=8 and r['hold']['sum']>0 and r['hold']['pf']>1.03 and r['hold_cost36']['sum']>=0]
    survivors.sort(key=lambda r:(r['hold_cost36']['sum']>0,r['hold']['pf'],r['hold']['mean']),reverse=True)
    payload={'method':{'dev':'Jan-May','validation':'Jun-Jul','holdout':'Aug','cost_base':.26,'cost_stress':[.36,.46],'one_position_at_a_time':True,'bracket_same_bar_rule':'SL first'},'counts':{'setups':len(setups),'exits':len(exits),'dev_viable':len(dev),'validation_viable':len(val),'frozen':len(frozen),'holdout_survivors':len(survivors)},'survivors':survivors,'frozen':results}
    (OUT/'walkforward_results.json').write_text(json.dumps(payload,indent=2))
    with (OUT/'walkforward_summary.md').open('w') as f:
        f.write('# XAUUSD Walk-Forward Search\n\n')
        f.write(f"Setups: {len(setups)}; exits: {len(exits)}; dev viable: {len(dev)}; validation viable: {len(val)}; frozen: {len(frozen)}; holdout survivors: {len(survivors)}.\n\n")
        for i,r in enumerate(survivors[:15],1):
            f.write(f"## Survivor {i}\n`{r['setup']}`  `{r['exit']}`  session={r['session']} direction={r['direction']}\n\n")
            for k in ('dev','val','hold','hold_cost36','hold_cost46'): f.write(f"- {k}: {r[k]}\n")
    print(json.dumps({'counts':payload['counts'],'top_survivors':survivors[:5]},indent=2))

if __name__=='__main__': main()
