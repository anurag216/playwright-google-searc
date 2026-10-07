#!/usr/bin/env python3
from __future__ import annotations
import csv,json,math,statistics,urllib.request
from collections import defaultdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_{ym}.csv'
DEV=[f'{y}_{m:02d}' for y in (2022,2023,2024) for m in range(1,13)]
VAL=[f'2025_{m:02d}' for m in range(1,13)]
HOLD=[f'2021_{m:02d}' for m in range(1,13)]
CHECK=[f'2026_{m:02d}' for m in range(1,9)]
ALL=HOLD+DEV+VAL+CHECK
OUT=Path('session_filter_output');DATA=OUT/'data';OUT.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True)

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
  a,z=A[t],B[t];b.append({'t':t,'day':t//86400000,'dow':(t//86400000+3)%7,'hr':(t//3600000)%24,'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2})
 tr=[0.0]*len(b);atr=[0.0]*len(b);s=0
 for i in range(1,len(b)):tr[i]=max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
 for i,x in enumerate(tr):
  s+=x
  if i>=20:s-=tr[i-20]
  atr[i]=s/min(i+1,20)
 av=[0.0]*len(b);s=0
 for i,x in enumerate(atr):
  s+=x
  if i>=240:s-=atr[i-240]
  av[i]=s/min(i+1,240)
 return b,atr,av

def events(data):
 b,a,av=data;days=defaultdict(list)
 for i,x in enumerate(b):days[x['day']].append(i)
 E=[]
 for idxs in days.values():
  R=[i for i in idxs if 6<=b[i]['hr']<12];W=[i for i in idxs if 12<=b[i]['hr']<17]
  if len(R)<30 or not W:continue
  rh=max(b[i]['h'] for i in R);rl=min(b[i]['l'] for i in R);at=max(a[R[-1]],.05)
  ro=b[R[0]]['o']; rc=b[R[-1]]['c']; rw=rh-rl
  br=None
  for wi,i in enumerate(W):
   if b[i]['c']<=rl-.3*at:br=(wi,i);break
  if not br:continue
  wi,bi=br
  for pos,j in enumerate(W[wi+1:wi+11],1):
   if b[j]['h']>=rl-.4*at and b[j]['c']<rl and b[j]['c']<b[j]['o'] and j+1<len(b):
    e=j+1
    if e<1500 or e+60>=len(b):break
    candle=max(b[j]['h']-b[j]['l'],1e-9)
    E.append({
      'i':e,'pnl_raw':b[e]['o']-b[e+60]['o'],
      'range_atr':rw/at,'range_dir':(rc-ro)/at,'vr':a[j]/max(av[j],1e-9),
      'r60':(b[j]['c']-b[j-60]['c'])/at,'r240':(b[j]['c']-b[j-240]['c'])/at,'r1440':(b[j]['c']-b[j-1440]['c'])/at,
      'break_depth':(rl-b[bi]['c'])/at,'retest_delay':pos,
      'rej_body':(b[j]['o']-b[j]['c'])/at,'rej_close':(rl-b[j]['c'])/at,
      'upper_wick':(b[j]['h']-max(b[j]['o'],b[j]['c']))/candle,
      'entry_hr':b[e]['hr'],'dow':b[e]['dow']
    });break
 return E

def stat(P):
 if not P:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
 gp=sum(x for x in P if x>0);gl=-sum(x for x in P if x<=0);eq=pk=dd=0
 for x in P:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {'n':len(P),'sum':sum(P),'mean':sum(P)/len(P),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in P)/len(P),'mdd':dd}

def gate(e,g):
 typ,x,y=g
 v=e[typ]
 if y=='ge':return v>=x
 if y=='le':return v<=x
 if y=='between':return x[0]<=v<=x[1]
 if y=='notdow':return e['dow']!=x
 return True

def gates():
 G=[('none',0,'ge')]
 specs={
 'range_atr':([2,3,4,5,6,8],['ge','le']),
 'range_dir':([-2,-1,0,1,2],['ge','le']),
 'vr':([.7,.9,1.0,1.1,1.3,1.5],['ge','le']),
 'r60':([-4,-2,-1,0,1,2],['ge','le']),
 'r240':([-8,-4,-2,0,2,4],['ge','le']),
 'r1440':([-15,-8,-4,0,4,8],['ge','le']),
 'break_depth':([.3,.5,.8,1.2,2],['ge','le']),
 'retest_delay':([2,4,6,8],['ge','le']),
 'rej_body':([.1,.25,.5,.8,1.2],['ge','le']),
 'rej_close':([0,.2,.5,.8],['ge','le']),
 'upper_wick':([.2,.4,.6],['ge','le']),
 'entry_hr':([13,14,15,16],['ge','le']),
 }
 for k,(vals,ops) in specs.items():
  for v in vals:
   for op in ops:G.append((k,v,op))
 for d in range(5):G.append(('dow',d,'notdow'))
 return G

def apply(events,gateset,cost):
 return [e['pnl_raw']-cost for e in events if all(g[0]=='none' or gate(e,g) for g in gateset)]

def eval_period(months,E,gateset,cost):
 P=[];M={}
 for m in months:
  p=apply(E[m],gateset,cost);M[m]=stat(p);P+=p
 return stat(P),M

def main():
 D={m:load(m) for m in ALL};E={m:events(D[m]) for m in ALL};G=gates()
 cand=[]
 combos=[(g,) for g in G if g[0]!='none']
 # two-gate combinations only after single gates rank
 singles=[]
 for gs in combos:
  st,M=eval_period(DEV,E,gs,.26);s46,_=eval_period(DEV,E,gs,.46)
  if st['n']>=120 and st['sum']>0 and st['pf']>1.04 and sum(M[m]['sum']>0 for m in DEV)>=20 and s46['sum']>0:
   sc=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1));singles.append((sc,gs))
 singles.sort(reverse=True)
 topg=[x[1][0] for x in singles[:20]]
 combos=[(g,) for g in topg]
 for i,g1 in enumerate(topg):
  for g2 in topg[i+1:]:
   if g1[0]!=g2[0]:combos.append((g1,g2))
 for gs in combos:
  st,M=eval_period(DEV,E,gs,.26);s46,_=eval_period(DEV,E,gs,.46)
  if st['n']<90 or st['sum']<=0 or st['pf']<=1.06 or sum(M[m]['sum']>0 for m in DEV)<20 or s46['sum']<=0:continue
  sc=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1));cand.append((sc,gs,st,M,s46))
 cand.sort(reverse=True,key=lambda x:x[0]);cand=cand[:80]
 V=[]
 for row in cand:
  sc,gs,dst,dM,d46=row;st,M=eval_period(VAL,E,gs,.26);s46,_=eval_period(VAL,E,gs,.46)
  if st['n']>=30 and st['sum']>0 and st['pf']>1.05 and sum(M[m]['sum']>0 for m in VAL)>=7 and s46['sum']>=0:
   vs=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1));V.append((vs,row,st,M,s46))
 V.sort(reverse=True,key=lambda x:x[0]);V=V[:20]
 R=[]
 for vs,row,vst,vM,v46 in V:
  sc,gs,dst,dM,d46=row;hst,hM=eval_period(HOLD,E,gs,.26);h46,_=eval_period(HOLD,E,gs,.46);c26,cM=eval_period(CHECK,E,gs,.26)
  R.append({'gates':gs,'dev':dst,'dev_pos_months':sum(dM[m]['sum']>0 for m in DEV),'val':vst,'val_pos_months':sum(vM[m]['sum']>0 for m in VAL),'hold2021':hst,'hold2021_pos_months':sum(hM[m]['sum']>0 for m in HOLD),'hold2021_46':h46,'check2026':c26,'check2026_pos_months':sum(cM[m]['sum']>0 for m in CHECK)})
 surv=[r for r in R if r['hold2021']['n']>=25 and r['hold2021']['sum']>0 and r['hold2021']['pf']>1.05 and r['hold2021_pos_months']>=6 and r['hold2021_46']['sum']>=0]
 surv.sort(key=lambda r:(r['hold2021_46']['sum'],r['hold2021']['pf']),reverse=True)
 out={'counts':{'single_dev':len(singles),'dev_candidates':len(cand),'val_finalists':len(V),'hold2021_survivors':len(surv)},'survivors':surv,'frozen':R}
 OUT.joinpath('filter_results.json').write_text(json.dumps(out,indent=2))
 OUT.joinpath('summary.md').write_text('# Frozen London-NY retest regime-filter search\n\n'+json.dumps(out['counts'],indent=2)+'\n\n'+json.dumps(surv[:10],indent=2))
 print(json.dumps({'counts':out['counts'],'top':surv[:5]},indent=2),flush=True)

if __name__=='__main__':main()
