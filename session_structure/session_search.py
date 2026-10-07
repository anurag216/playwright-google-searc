#!/usr/bin/env python3
from __future__ import annotations
import csv,json,math,urllib.request
from dataclasses import dataclass,asdict
from pathlib import Path
from collections import defaultdict

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_{ym}.csv'
DEV=[f'{y}_{m:02d}' for y in (2023,2024) for m in range(1,13)]
VAL=[f'2025_{m:02d}' for m in range(1,13)]
HOLD=[f'2026_{m:02d}' for m in range(1,9)]
ALL=DEV+VAL+HOLD
OUT=Path('session_output');DATA=OUT/'data';OUT.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup:
    pattern:str; session:str; p:tuple
@dataclass(frozen=True)
class Exit:
    kind:str;p:tuple
@dataclass
class Sig:
    i:int;d:int;px:float;atr:float

SESSIONS={
 'asia06_london':(0,6,6,11),
 'asia07_london':(0,7,7,12),
 'asia1_6_london':(1,6,6,11),
 'london_ny':(6,12,12,17),
 'london7_ny':(7,12,12,17),
}

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
    for i in range(1,len(b)):
        tr[i]=max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    return b,atr

def setups():
    q=[]
    for sn in SESSIONS:
      for buf in (0,.15,.3,.5):q.append(Setup('break',sn,(buf,)))
      for buf in (.1,.25,.5):
       for wick in (.4,.6,.75):q.append(Setup('sweep',sn,(buf,wick)))
      for buf in (0,.15,.3):
       for band in (.2,.4):
        for wait in (5,10):q.append(Setup('retest',sn,(buf,band,wait)))
    return q

def exits():
    x=[Exit('hold',(h,)) for h in (10,20,30,60)]
    for tp in (1,1.5,2):
     for sl in (.75,1,1.25):
      for mh in (15,30,60):x.append(Exit('bracket',(tp,sl,mh)))
    return x

def gen(data,s):
    b,a=data;rs,re,ws,we=SESSIONS[s.session];days=defaultdict(list)
    for i,x in enumerate(b):days[x['day']].append(i)
    out=[]
    for idxs in days.values():
        R=[i for i in idxs if rs<=b[i]['hr']<re];W=[i for i in idxs if ws<=b[i]['hr']<we]
        if len(R)<30 or not W:continue
        rh=max(b[i]['h'] for i in R);rl=min(b[i]['l'] for i in R);at=max(a[R[-1]],.05)
        if s.pattern=='break':
            buf=s.p[0]*at
            for i in W:
                if b[i]['c']>rh+buf and i+1<len(b):out.append(Sig(i+1,1,b[i+1]['o'],max(a[i],.05)));break
                if b[i]['c']<rl-buf and i+1<len(b):out.append(Sig(i+1,-1,b[i+1]['o'],max(a[i],.05)));break
        elif s.pattern=='sweep':
            buf,wick=s.p;buf*=at
            for i in W:
                rg=b[i]['h']-b[i]['l']
                if rg<=0:continue
                if b[i]['h']>rh+buf and b[i]['c']<rh and (b[i]['h']-b[i]['c'])/rg>=wick and i+1<len(b):out.append(Sig(i+1,-1,b[i+1]['o'],max(a[i],.05)));break
                if b[i]['l']<rl-buf and b[i]['c']>rl and (b[i]['c']-b[i]['l'])/rg>=wick and i+1<len(b):out.append(Sig(i+1,1,b[i+1]['o'],max(a[i],.05)));break
        else:
            buf,band,wait=s.p;buf*=at;band*=at
            br=None
            for wi,i in enumerate(W):
                if b[i]['c']>rh+buf:br=(wi,i,1,rh);break
                if b[i]['c']<rl-buf:br=(wi,i,-1,rl);break
            if not br:continue
            wi,ii,d,lv=br
            for j in W[wi+1:wi+1+int(wait)]:
                if d==1 and b[j]['l']<=lv+band and b[j]['c']>lv and b[j]['c']>b[j]['o'] and j+1<len(b):out.append(Sig(j+1,1,b[j+1]['o'],max(a[j],.05)));break
                if d==-1 and b[j]['h']>=lv-band and b[j]['c']<lv and b[j]['c']<b[j]['o'] and j+1<len(b):out.append(Sig(j+1,-1,b[j+1]['o'],max(a[j],.05)));break
    return sorted(out,key=lambda x:x.i)

def stat(P):
    if not P:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in P if x>0);gl=-sum(x for x in P if x<=0);eq=pk=dd=0
    for x in P:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(P),'sum':sum(P),'mean':sum(P)/len(P),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in P)/len(P),'mdd':dd}

def sim(data,S,ex,side,cost):
    b=data[0];P=[];busy=-1
    for x in S:
        if x.i<=busy or (side and x.d!=side):continue
        if ex.kind=='hold':
            e=x.i+ex.p[0]
            if e>=len(b):continue
            gross=x.d*(b[e]['o']-x.px);busy=e
        else:
            tm,sm,mh=ex.p;tp=max(.05,tm*x.atr);sl=max(.05,sm*x.atr);last=min(len(b)-1,x.i+mh);gross=None;busy=last
            for j in range(x.i,last+1):
                ht=b[j]['h']>=x.px+tp if x.d==1 else b[j]['l']<=x.px-tp
                hs=b[j]['l']<=x.px-sl if x.d==1 else b[j]['h']>=x.px+sl
                if ht and hs:gross=-sl;busy=j;break
                if hs:gross=-sl;busy=j;break
                if ht:gross=tp;busy=j;break
            if gross is None:gross=x.d*(b[last]['c']-x.px)
        P.append(gross-cost)
    return P

def agg(months,D,S,ex,side,cost):
    P=[];M={}
    for m in months:
        p=sim(D[m],S[m],ex,side,cost);M[m]=stat(p);P+=p
    return stat(P),M

def main():
    D={m:load(m) for m in ALL};Q=setups();E=exits();print('loaded months',len(ALL),'setups',len(Q),'exits',len(E),flush=True)
    dev=[]
    for qi,q in enumerate(Q):
        S={m:gen(D[m],q) for m in DEV}
        for ex in E:
         for side in (0,1,-1):
            st,M=agg(DEV,D,S,ex,side,.26)
            if st['n']<100 or st['sum']<=0 or st['pf']<=1.05 or sum(M[m]['sum']>0 for m in DEV)<14:continue
            s46,_=agg(DEV,D,S,ex,side,.46)
            if s46['sum']<=0:continue
            score=(st['pf']-1)*(st['n']**.5)*st['mean']/(1+st['mdd']/max(st['sum'],1))
            dev.append((score,qi,ex,side,st,M,s46))
    dev.sort(reverse=True,key=lambda x:x[0]);dev=dev[:150];print('dev finalists',len(dev),flush=True)
    ids={r[1] for r in dev};SV={i:{m:gen(D[m],Q[i]) for m in VAL} for i in ids};V=[]
    for r in dev:
        sc,i,ex,side,dst,dM,d46=r;st,M=agg(VAL,D,SV[i],ex,side,.26);s46,_=agg(VAL,D,SV[i],ex,side,.46)
        if st['n']>=40 and st['sum']>0 and st['pf']>1.05 and sum(M[m]['sum']>0 for m in VAL)>=7 and s46['sum']>=0:
            vs=(st['pf']-1)*(st['n']**.5)*st['mean']/(1+st['mdd']/max(st['sum'],1));V.append((vs,r,st,M,s46))
    V.sort(reverse=True,key=lambda x:x[0]);V=V[:25];print('validation finalists',len(V),flush=True)
    ids={x[1][1] for x in V};SH={i:{m:gen(D[m],Q[i]) for m in HOLD} for i in ids};R=[]
    for vs,r,vst,vM,v46 in V:
        sc,i,ex,side,dst,dM,d46=r;st,M=agg(HOLD,D,SH[i],ex,side,.26);s46,_=agg(HOLD,D,SH[i],ex,side,.46)
        R.append({'setup':asdict(Q[i]),'exit':asdict(ex),'side':side,'dev':dst,'dev_pos_months':sum(dM[m]['sum']>0 for m in DEV),'val':vst,'val_pos_months':sum(vM[m]['sum']>0 for m in VAL),'holdout':st,'holdout_pos_months':sum(M[m]['sum']>0 for m in HOLD),'holdout46':s46,'holdout_monthly':M})
    surv=[r for r in R if r['holdout']['n']>=25 and r['holdout']['sum']>0 and r['holdout']['pf']>1.05 and r['holdout_pos_months']>=5 and r['holdout46']['sum']>=0]
    surv.sort(key=lambda r:(r['holdout46']['sum'],r['holdout']['pf']),reverse=True)
    out={'counts':{'dev_finalists':len(dev),'val_finalists':len(V),'survivors':len(surv)},'survivors':surv,'frozen':R}
    OUT.joinpath('session_results.json').write_text(json.dumps(out,indent=2))
    OUT.joinpath('summary.md').write_text('# Session structure search\n\n'+json.dumps(out['counts'],indent=2)+'\n\n'+json.dumps(surv[:10],indent=2))
    print(json.dumps({'counts':out['counts'],'top':surv[:5]},indent=2),flush=True)

if __name__=='__main__':main()
