#!/usr/bin/env python3
from __future__ import annotations
import csv, json, urllib.request
from collections import defaultdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_{ym}.csv'
YEARS={
 'extra':[f'{y}_{m:02d}' for y in (2019,2020) for m in range(1,13)],
 'hold2021':[f'2021_{m:02d}' for m in range(1,13)],
 'dev':[f'{y}_{m:02d}' for y in (2022,2023,2024) for m in range(1,13)],
 'val2025':[f'2025_{m:02d}' for m in range(1,13)],
 'check2026':[f'2026_{m:02d}' for m in range(1,9)],
}
ALL=sum(YEARS.values(),[])
OUT=Path('session_robustness_output'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

def read(ym,side):
 p=DATA/f'{side}_{ym}.csv'
 if not p.exists(): urllib.request.urlretrieve(BASE.format(side=side,ym=ym),p)
 q={}
 with p.open() as f:
  for z in csv.DictReader(f):
   q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
 return q

def load(ym):
 A,B=read(ym,'ask'),read(ym,'bid'); b=[]
 for t in sorted(set(A)&set(B)):
  a,z=A[t],B[t]
  b.append({
   't':t,'day':t//86400000,'hr':(t//3600000)%24,
   'ao':a[0],'ah':a[1],'al':a[2],'ac':a[3],
   'bo':z[0],'bh':z[1],'bl':z[2],'bc':z[3],
   'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2
  })
 tr=[0.0]*len(b); atr=[0.0]*len(b); s=0.0
 for i in range(1,len(b)):
  tr[i]=max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
 for i,x in enumerate(tr):
  s+=x
  if i>=20:s-=tr[i-20]
  atr[i]=s/min(i+1,20)
 av=[0.0]*len(b); s=0.0
 for i,x in enumerate(atr):
  s+=x
  if i>=240:s-=atr[i-240]
  av[i]=s/min(i+1,240)
 return b,atr,av

def events(data,side):
 b,a,av=data; days=defaultdict(list); out=[]
 for i,x in enumerate(b): days[x['day']].append(i)
 for idxs in days.values():
  R=[i for i in idxs if 6<=b[i]['hr']<12]
  W=[i for i in idxs if 12<=b[i]['hr']<17]
  if len(R)<30 or not W: continue
  rh=max(b[i]['h'] for i in R); rl=min(b[i]['l'] for i in R)
  at=max(a[R[-1]],.05)
  br=None
  if side=='short':
   for wi,i in enumerate(W):
    if b[i]['c']<=rl-.3*at: br=(wi,i); break
  else:
   for wi,i in enumerate(W):
    if b[i]['c']>=rh+.3*at: br=(wi,i); break
  if not br: continue
  wi,bi=br
  for pos,j in enumerate(W[wi+1:wi+11],1):
   if j<1500 or j+120>=len(b): break
   if side=='short':
    ok=(b[j]['h']>=rl-.4*at and b[j]['c']<rl and b[j]['c']<b[j]['o'])
    break_depth=(rl-b[bi]['c'])/at
    rej_close=(rl-b[j]['c'])/at
   else:
    ok=(b[j]['l']<=rh+.4*at and b[j]['c']>rh and b[j]['c']>b[j]['o'])
    break_depth=(b[bi]['c']-rh)/at
    rej_close=(b[j]['c']-rh)/at
   if not ok: continue
   e=j+1
   out.append({
    'i':e,'side':side,'atr':at,'month':None,
    'r240':(b[j]['c']-b[j-240]['c'])/at,
    'r1440':(b[j]['c']-b[j-1440]['c'])/at,
    'vr':a[j]/max(av[j],1e-9),
    'break_depth':break_depth,'rej_close':rej_close,
    'entry_hr':b[e]['hr'],
   })
   break
 return out

def stat(P):
 if not P:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
 gp=sum(x for x in P if x>0); gl=-sum(x for x in P if x<=0)
 eq=pk=dd=0.0
 for x in P:
  eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
 return {'n':len(P),'sum':sum(P),'mean':sum(P)/len(P),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in P)/len(P),'mdd':dd}

def primary_gate(e):
 if e['side']=='short': return e['r240']<=-8 and e['break_depth']<=2
 return e['r240']>=8 and e['break_depth']<=2

def variant_gate(e,r240_cut,depth):
 if e['side']=='short': return e['r240']<=-r240_cut and e['break_depth']<=depth
 return e['r240']>=r240_cut and e['break_depth']<=depth

def pnl_mid(b,e,hold,cost):
 i=e['i']; x=i+hold
 if x>=len(b):return None
 raw=(b[i]['o']-b[x]['o']) if e['side']=='short' else (b[x]['o']-b[i]['o'])
 return raw-cost

def pnl_native(b,e,hold):
 i=e['i']; x=i+hold
 if x>=len(b):return None
 if e['side']=='short': return b[i]['bo']-b[x]['ao']
 return b[x]['bo']-b[i]['ao']

def eval_month(b,ev,hold=60,cost=.26,native=False,gate=primary_gate):
 P=[]
 for e in ev:
  if not gate(e):continue
  x=pnl_native(b,e,hold) if native else pnl_mid(b,e,hold,cost)
  if x is not None:P.append(x)
 return stat(P)

def aggregate(months,D,E,side,hold=60,cost=.26,native=False,gate=primary_gate):
 P=[]; monthly={}
 for m in months:
  st=eval_month(D[m][0],E[(m,side)],hold,cost,native,gate)
  monthly[m]=st
  # recompute pnl list for aggregation
  for e in E[(m,side)]:
   if not gate(e):continue
   x=pnl_native(D[m][0],e,hold) if native else pnl_mid(D[m][0],e,hold,cost)
   if x is not None:P.append(x)
 return stat(P),monthly

def compact_period(name,months,D,E,side):
 base,mon=aggregate(months,D,E,side,60,.26,False)
 c46,_=aggregate(months,D,E,side,60,.46,False)
 c66,_=aggregate(months,D,E,side,60,.66,False)
 nat,_=aggregate(months,D,E,side,60,.26,True)
 return {
  'period':name,'side':side,'base26':base,'cost46':c46,'cost66':c66,'native_bidask':nat,
  'positive_months':sum(mon[m]['sum']>0 for m in months),'months':len(months)
 }

def main():
 D={};E={}
 for k,m in enumerate(ALL,1):
  D[m]=load(m); E[(m,'short')]=events(D[m],'short'); E[(m,'long')]=events(D[m],'long')
  if k%12==0: print('loaded',k,'months',flush=True)

 periods=[]
 for name,months in YEARS.items():
  periods.append(compact_period(name,months,D,E,'short'))
  periods.append(compact_period(name,months,D,E,'long'))

 # hold-time robustness for frozen short rule; no selection performed here.
 holds={}
 for h in (30,45,60,75,90):
  holds[str(h)]={}
  for name,months in YEARS.items():
   holds[str(h)][name]=aggregate(months,D,E,'short',h,.26,False)[0]

 # threshold neighborhood around frozen (-8, depth<=2), reported without re-selection.
 sensitivity={}
 for rc in (6,8,10):
  for depth in (1.5,2.0,2.5):
   key=f'r240_{rc}_depth_{depth}'
   sensitivity[key]={}
   gate=lambda e,rc=rc,depth=depth: variant_gate(e,rc,depth)
   for name,months in YEARS.items():
    sensitivity[key][name]=aggregate(months,D,E,'short',60,.26,False,gate)[0]

 # combined frozen short+mirror long, month by month
 combined={}
 for name,months in YEARS.items():
  P=[];pm=0
  for m in months:
   p=[]
   for side in ('short','long'):
    for e in E[(m,side)]:
     if not primary_gate(e):continue
     x=pnl_mid(D[m][0],e,60,.26)
     if x is not None:p.append(x)
   P.extend(p)
   if sum(p)>0:pm+=1
  combined[name]={'stats':stat(P),'positive_months':pm,'months':len(months)}

 out={
  'frozen_rule':{
   'session_range':'06:00-12:00 UTC',
   'trade_window':'12:00-17:00 UTC',
   'break':'first close >=0.3 ATR beyond London range',
   'retest':'within next 10 minutes; retest within 0.4 ATR of broken boundary; rejection closes outside range in breakout direction',
   'entry':'next M1 open',
   'hold_minutes':60,
   'short_filter':'r240 <= -8 and break_depth <= 2 ATR',
   'long_mirror_filter':'r240 >= +8 and break_depth <= 2 ATR',
   'synthetic_costs':[.26,.46,.66],
  },
  'period_results':periods,
  'hold_robustness_short':holds,
  'threshold_sensitivity_short':sensitivity,
  'combined_short_long':combined,
 }
 OUT.joinpath('robustness_results.json').write_text(json.dumps(out,indent=2))
 with OUT.joinpath('summary.md').open('w') as f:
  f.write('# Frozen London-NY retest robustness check\n\n')
  f.write('No parameters are selected on the extra/holdout/check periods.\n\n')
  for r in periods:
   f.write(f"## {r['period']} — {r['side']}\n")
   f.write(f"- base .26: {r['base26']}\n- cost .46: {r['cost46']}\n- cost .66: {r['cost66']}\n- native bid/ask: {r['native_bidask']}\n- positive months: {r['positive_months']}/{r['months']}\n\n")
  f.write('## Combined short + mirrored long\n')
  for k,v in combined.items(): f.write(f"- {k}: {v}\n")
 print(json.dumps({'period_results':periods,'combined':combined,'hold60':{k:v['60'] if '60' in v else None for k,v in {}}},indent=2),flush=True)

if __name__=='__main__':main()
