#!/usr/bin/env python3
from __future__ import annotations
import csv,json,math,urllib.request
from collections import defaultdict
from dataclasses import dataclass,asdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_{ym}.csv'
DEV=[f'{y}_{m:02d}' for y in (2022,2023,2024) for m in range(1,13)]
VAL=[f'2025_{m:02d}' for m in range(1,13)]
HOLD=[f'2021_{m:02d}' for m in range(1,13)]
CHECK=[f'2026_{m:02d}' for m in range(1,9)]
ALL=HOLD+DEV+VAL+CHECK
OUT=Path('campaign_output');DATA=OUT/'data';OUT.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Campaign:
 hold:int
 stop_atr:float
 add_levels:tuple
 add_size:float

def read(ym,side):
 p=DATA/f'{side}_{ym}.csv'
 if not p.exists():urllib.request.urlretrieve(BASE.format(side=side,ym=ym),p)
 q={}
 with p.open() as f:
  for z in csv.DictReader(f):q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
 return q

def load(ym):
 A,B=read(ym,'ask'),read(ym,'bid');b=[]
 for t in sorted(set(A)&set(B)):
  a,z=A[t],B[t];b.append({'t':t,'day':t//86400000,'hr':(t//3600000)%24,'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2})
 tr=[0.0]*len(b);atr=[0.0]*len(b);s=0
 for i in range(1,len(b)):tr[i]=max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
 for i,x in enumerate(tr):
  s+=x
  if i>=20:s-=tr[i-20]
  atr[i]=s/min(i+1,20)
 return b,atr

def events(data):
 b,a=data;days=defaultdict(list);E=[]
 for i,x in enumerate(b):days[x['day']].append(i)
 for idxs in days.values():
  R=[i for i in idxs if 6<=b[i]['hr']<12];W=[i for i in idxs if 12<=b[i]['hr']<17]
  if len(R)<30 or not W:continue
  rl=min(b[i]['l'] for i in R);at=max(a[R[-1]],.05);br=None
  for wi,i in enumerate(W):
   if b[i]['c']<=rl-.3*at:br=(wi,i);break
  if not br:continue
  wi,bi=br
  for j in W[wi+1:wi+11]:
   if j<1500 or j+120>=len(b):break
   if b[j]['h']>=rl-.4*at and b[j]['c']<rl and b[j]['c']<b[j]['o']:
    r240=(b[j]['c']-b[j-240]['c'])/at
    depth=(rl-b[bi]['c'])/at
    if r240<=-8 and depth<=2:
     E.append({'i':j+1,'atr':at})
    break
 return E

def stat(P):
 if not P:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
 gp=sum(x for x in P if x>0);gl=-sum(x for x in P if x<=0);eq=pk=dd=0
 for x in P:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {'n':len(P),'sum':sum(P),'mean':sum(P)/len(P),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in P)/len(P),'mdd':dd}

def one(b,e,camp,cost):
 i=e['i']; atr=e['atr']; base=b[i]['o']; used=set(); end=min(len(b)-1,i+camp.hold)
 max_exposure=1.0+len(camp.add_levels)*camp.add_size
 initial_size=1.0/max_exposure
 add_abs=camp.add_size/max_exposure
 legs=[(base,initial_size)]
 stop=base+camp.stop_atr*atr if camp.stop_atr>0 else None
 exit_px=None
 # Adds only after a CLOSE proves favorable progress; execute at next bar open.
 for j in range(i,end):
  if stop is not None and b[j]['h']>=stop:
   exit_px=stop;end=j;break
  prog=base-b[j]['c']
  for level in camp.add_levels:
   if level in used:continue
   if prog>=level*atr and j+1<=end:
    px=b[j+1]['o']
    # Add only if next-open execution is still favorable vs initial entry.
    if px<base:
     legs.append((px,add_abs));used.add(level)
  # no same-bar add then stop optimism: stop is checked before add above
 if exit_px is None:exit_px=b[end]['o']
 pnl=sum(sz*(ep-exit_px-cost) for ep,sz in legs)
 return pnl,len(legs),sum(sz for _,sz in legs)

def eval_month(b,E,camp,cost):
 P=[];leg_counts=[];exposure=[]
 for e in E:
  p,n,v=one(b,e,camp,cost);P.append(p);leg_counts.append(n);exposure.append(v)
 s=stat(P)
 s['avg_legs']=sum(leg_counts)/len(leg_counts) if leg_counts else 0
 s['avg_exposure']=sum(exposure)/len(exposure) if exposure else 0
 s['max_legs']=max(leg_counts) if leg_counts else 0
 return s,P

def aggregate(months,D,E,camp,cost):
 P=[];M={}
 for m in months:
  s,p=eval_month(D[m][0],E[m],camp,cost);M[m]=s;P+=p
 return stat(P),M

def campaigns():
 q=[]
 levels=[(),(.5,),(1.0,),(.5,1.0),(1.0,2.0),(.5,1.0,1.5)]
 for hold in (45,60):
  for stop in (0,1.5,2.0,2.5,3.0):
   for lev in levels:
    for sz in ((0.5,1.0) if lev else (0.5,)):
     q.append(Campaign(hold,stop,lev,sz))
 return q

def score(st,mon,stress):
 pos=sum(mon[m]['sum']>0 for m in mon)
 if st['n']<100 or st['sum']<=0 or st['pf']<1.2 or pos<20 or stress['sum']<=0:return None
 return (st['pf']-1)*st['sum']/(1+st['mdd'])*(1+pos/36)

def main():
 D={m:load(m) for m in ALL};E={m:events(D[m]) for m in ALL}
 Q=campaigns();dev=[]
 for c in Q:
  st,M=aggregate(DEV,D,E,c,.26);s46,_=aggregate(DEV,D,E,c,.46);sc=score(st,M,s46)
  if sc is not None:dev.append((sc,c,st,M,s46))
 dev.sort(reverse=True,key=lambda x:x[0]);top=dev[:30]
 V=[]
 for row in top:
  sc,c,dst,dM,d46=row;v,vM=aggregate(VAL,D,E,c,.26);v46,_=aggregate(VAL,D,E,c,.46)
  if v['n']>=25 and v['sum']>0 and v['pf']>1.2 and v46['sum']>=0:
   vs=(v['pf']-1)*v['sum']/(1+v['mdd']);V.append((vs,row,v,vM,v46))
 V.sort(reverse=True,key=lambda x:x[0]);frozen=V[:12]
 R=[]
 for vs,row,v,vM,v46 in frozen:
  sc,c,dst,dM,d46=row;h,hM=aggregate(HOLD,D,E,c,.26);h46,_=aggregate(HOLD,D,E,c,.46);ck,ckM=aggregate(CHECK,D,E,c,.26);ck46,_=aggregate(CHECK,D,E,c,.46)
  R.append({'campaign':asdict(c),'dev':dst,'dev_cost46':d46,'val':v,'val_cost46':v46,'hold2021':h,'hold2021_cost46':h46,'check2026':ck,'check2026_cost46':ck46,'hold_pos_months':sum(hM[m]['sum']>0 for m in HOLD),'check_pos_months':sum(ckM[m]['sum']>0 for m in CHECK)})
 surv=[r for r in R if r['hold2021']['sum']>0 and r['hold2021']['pf']>1.1 and r['hold2021_cost46']['sum']>=0 and r['check2026']['sum']>0 and r['check2026']['pf']>1.2]
 surv.sort(key=lambda r:(r['check2026_cost46']['sum'],r['hold2021_cost46']['sum'],r['val']['pf']),reverse=True)
 # explicit non-pyramid references
 refs=[]
 for c in [Campaign(45,0,(),.5),Campaign(60,0,(),.5)]:
  item={'campaign':asdict(c)}
  for name,months in [('dev',DEV),('val',VAL),('hold2021',HOLD),('check2026',CHECK)]:
   item[name]=aggregate(months,D,E,c,.26)[0]
  refs.append(item)
 out={'counts':{'campaigns':len(Q),'dev_viable':len(dev),'validation_viable':len(V),'frozen':len(frozen),'survivors':len(surv)},'references':refs,'survivors':surv,'frozen':R}
 OUT.joinpath('campaign_results.json').write_text(json.dumps(out,indent=2))
 OUT.joinpath('summary.md').write_text('# Frozen signal campaign-management search — equal max exposure\n\n'+json.dumps(out['counts'],indent=2)+'\n\n## References\n'+json.dumps(refs,indent=2)+'\n\n## Survivors\n'+json.dumps(surv[:10],indent=2))
 print(json.dumps({'counts':out['counts'],'references':refs,'top':surv[:5]},indent=2),flush=True)

if __name__=='__main__':main()
