#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_{ym}.csv'
DEV=[f'2025_{m:02d}' for m in range(1,13)]+[f'2026_{m:02d}' for m in range(1,4)]
VAL=[f'2026_{m:02d}' for m in range(4,7)]
HOLD=[f'2024_{m:02d}' for m in range(1,13)]
ALL=DEV+VAL+HOLD
SESS={'all':(0,24),'london_ny':(6,17),'us':(12,22),'ny_overlap':(12,17)}
OUT=Path('regime_output');DATA=OUT/'data';OUT.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup: p:tuple
@dataclass
class Sig: i:int;d:int;px:float;atr:float;hr:int;r60:float;r240:float;r1440:float;vr:float

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
        a,z=A[t],B[t];b.append({'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2,'hr':(t//3600000)%24})
    c=[x['c'] for x in b];h=[x['h'] for x in b];l=[x['l'] for x in b];tr=[0]*len(b);atr=[0]*len(b);s=0
    for i in range(1,len(b)):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    av=[0]*len(b);s=0
    for i,x in enumerate(atr):
        s+=x
        if i>=240:s-=atr[i-240]
        av[i]=s/min(i+1,240)
    return b,c,atr,av

def eff(c,i,w):
    p=sum(abs(c[k]-c[k-1]) for k in range(i-w+1,i+1));return abs(c[i]-c[i-w])/(p+1e-12)

def setups():
    q=[]
    for n in (10,20):
     for k in (2.0,3.0,4.0):
      for e in (.5,.7):
       for pb in (.4,.6):
        for ret in (.2,.4):
         for wait in (3,5):q.append(Setup((n,k,e,pb,ret,wait)))
    return q

def gen(d,s):
    b,c,a,av=d; n,k,ee,pb,ret,wait=s.p;out=[]
    for i in range(max(1500,n+2),len(b)-8):
        mv=c[i]-c[i-n];dd=1 if mv>0 else -1 if mv<0 else 0;at=max(a[i],.05)
        if not dd or abs(mv)<k*at or eff(c,i,n)<ee:continue
        base,peak=c[i-n],c[i];r=-1
        for j in range(i+1,min(len(b)-2,i+wait+1)):
            if dd*(peak-c[j])>=pb*abs(mv) and dd*(c[j]-base)>=ret*abs(mv):r=j;break
        if r<0:continue
        j=r+1
        if (c[j]-c[j-1])*dd<=0 or dd*(c[j]-base)<ret*abs(mv):continue
        eidx=j+1
        r60=c[j]-c[j-60];r240=c[j]-c[j-240];r1440=c[j]-c[j-1440];vr=a[j]/max(av[j],1e-9)
        out.append(Sig(eidx,dd,b[eidx]['o'],at,b[eidx]['hr'],r60,r240,r1440,vr))
    return out

GATES=[]
for base in ('none','align60','align240','align1440','align60_240','align240_1440','align_all','counter60','counter240'):
    GATES.append((base,0))
for base in ('align60','align240','align60_240','align240_1440'):
    for v in (.8,1.0,1.2,1.5):GATES.append((base,v))
for tf in ('60','240','1440'):
    for k in (2,4,6):GATES.append((f'strong{tf}',k))

def gate(x,g):
    name,v=g;d=x.d
    if name=='none':ok=True
    elif name=='align60':ok=d*x.r60>0
    elif name=='align240':ok=d*x.r240>0
    elif name=='align1440':ok=d*x.r1440>0
    elif name=='align60_240':ok=d*x.r60>0 and d*x.r240>0
    elif name=='align240_1440':ok=d*x.r240>0 and d*x.r1440>0
    elif name=='align_all':ok=d*x.r60>0 and d*x.r240>0 and d*x.r1440>0
    elif name=='counter60':ok=d*x.r60<0
    elif name=='counter240':ok=d*x.r240<0
    elif name=='strong60':ok=d*x.r60>v*x.atr
    elif name=='strong240':ok=d*x.r240>v*x.atr
    else:ok=d*x.r1440>v*x.atr
    if v and name.startswith('align'):ok=ok and x.vr>=v
    return ok

def stat(p):
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0
    for x in p:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def sim(d,S,hold,se,g,cost):
    b=d[0];lo,hi=SESS[se];P=[];busy=-1
    for x in S:
        if x.i<=busy or not(lo<=x.hr<hi) or not gate(x,g):continue
        e=x.i+hold
        if e>=len(b):break
        P.append(x.d*(b[e]['o']-x.px)-cost);busy=e
    return P

def agg(months,D,S,hold,se,g,cost):
    P=[];M={}
    for m in months:
        p=sim(D[m],S[m],hold,se,g,cost);M[m]=stat(p);P+=p
    return stat(P),M

def main():
    D={m:load(m) for m in ALL};Q=setups();print('loaded',len(ALL),'months setups',len(Q),'gates',len(GATES),flush=True)
    dev=[]
    for qi,q in enumerate(Q):
        S={m:gen(D[m],q) for m in DEV}
        for hold in (5,10,20):
         for se in SESS:
          for g in GATES:
            st,M=agg(DEV,D,S,hold,se,g,.26)
            if st['n']<100 or st['sum']<=0 or st['pf']<=1.05 or sum(M[m]['sum']>0 for m in DEV)<9:continue
            s46,_=agg(DEV,D,S,hold,se,g,.46)
            if s46['sum']<=0:continue
            score=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1))
            dev.append((score,qi,hold,se,g,st,M,s46))
        if (qi+1)%20==0:print('dev setup',qi+1,flush=True)
    dev.sort(reverse=True,key=lambda x:x[0]);dev=dev[:150];print('dev finalists',len(dev),flush=True)
    ids={r[1] for r in dev};SV={i:{m:gen(D[m],Q[i]) for m in VAL} for i in ids};V=[]
    for r in dev:
        sc,i,h,se,g,dst,dM,d46=r;st,M=agg(VAL,D,SV[i],h,se,g,.26);s46,_=agg(VAL,D,SV[i],h,se,g,.46)
        if st['n']>=20 and st['sum']>0 and st['pf']>1.05 and sum(M[m]['sum']>0 for m in VAL)>=2 and s46['sum']>=0:
            vs=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1));V.append((vs,r,st,M,s46))
    V.sort(reverse=True,key=lambda x:x[0]);V=V[:25];print('validation finalists',len(V),flush=True)
    ids={r[1][1] for r in V};SH={i:{m:gen(D[m],Q[i]) for m in HOLD} for i in ids};R=[]
    for vs,r,vst,vM,v46 in V:
        sc,i,h,se,g,dst,dM,d46=r;st,M=agg(HOLD,D,SH[i],h,se,g,.26);s46,_=agg(HOLD,D,SH[i],h,se,g,.46)
        R.append({'setup':asdict(Q[i]),'hold':h,'session':se,'gate':g,'dev':dst,'dev_pos_months':sum(dM[m]['sum']>0 for m in DEV),'val':vst,'val_pos_months':sum(vM[m]['sum']>0 for m in VAL),'holdout':st,'holdout_pos_months':sum(M[m]['sum']>0 for m in HOLD),'holdout46':s46,'holdout_monthly':M})
    surv=[r for r in R if r['holdout']['n']>=50 and r['holdout']['sum']>0 and r['holdout']['pf']>1.05 and r['holdout_pos_months']>=7 and r['holdout46']['sum']>=0]
    surv.sort(key=lambda r:(r['holdout46']['sum'],r['holdout']['pf']),reverse=True)
    out={'counts':{'dev_finalists':len(dev),'val_finalists':len(V),'survivors':len(surv)},'survivors':surv,'frozen':R}
    OUT.joinpath('regime_results.json').write_text(json.dumps(out,indent=2))
    OUT.joinpath('summary.md').write_text('# Regime-adaptive IPR search\n\n'+json.dumps(out['counts'],indent=2)+'\n\n'+json.dumps(surv[:10],indent=2))
    print(json.dumps({'counts':out['counts'],'top':surv[:5]},indent=2),flush=True)

if __name__=='__main__':main()
