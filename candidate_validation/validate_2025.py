#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, random, statistics, urllib.request
from pathlib import Path
from collections import defaultdict

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2025_{month}.csv'
MONTHS=[f'{i:02d}' for i in range(1,13)]
OUT=Path('candidate_2025_output'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

def side(m,s):
    p=DATA/f'{s}_{m}.csv'
    if not p.exists(): urllib.request.urlretrieve(BASE.format(side=s,month=m),p)
    q={}
    with p.open() as f:
        for z in csv.DictReader(f): q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
    return q

def load(m):
    A,B=side(m,'ask'),side(m,'bid'); b=[]
    for t in sorted(set(A)&set(B)):
        a,z=A[t],B[t]
        b.append({'t':t,'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2,'hr':(t//3600000)%24,'day':t//86400000})
    c=[x['c'] for x in b];h=[x['h'] for x in b];l=[x['l'] for x in b];tr=[0.0]*len(b);atr=[0.0]*len(b);s=0
    for i in range(1,len(b)):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    return b,c,atr

def eff(c,i,w=20):
    p=sum(abs(c[k]-c[k-1]) for k in range(i-w+1,i+1))
    return abs(c[i]-c[i-w])/(p+1e-12)

def signals(data):
    b,c,a=data; out=[]; N=len(b)
    for i in range(65,N-8):
        mv=c[i]-c[i-20]
        if mv>=0:continue
        at=max(a[i],.05)
        if abs(mv)<1.5*at or eff(c,i,20)<.50:continue
        base,peak=c[i-20],c[i];r=-1
        for j in range(i+1,min(N-2,i+6)):
            if -(peak-c[j])>=.40*abs(mv) and -(c[j]-base)>=.20*abs(mv):
                r=j;break
        if r<0:continue
        j=r+1
        if c[j]-c[j-1]<0 and -(c[j]-base)>=.20*abs(mv):
            e=j+1
            if 6<=b[e]['hr']<17:out.append(e)
    return out

def trades(data,idx,cost):
    b=data[0]; P=[];busy=-1
    for e in idx:
        if e<=busy or e+10>=len(b):continue
        gross=b[e]['o']-b[e+10]['o']
        pnl=gross-cost
        P.append({'pnl':pnl,'day':b[e]['day'],'entry_t':b[e]['t'],'entry':b[e]['o'],'exit':b[e+10]['o']})
        busy=e+10
    return P

def stats(T):
    p=[x['pnl'] for x in T]
    if not p:return {'n':0,'sum':0,'mean':0,'median':0,'pf':0,'win':0,'mdd':0,'max_loss_streak':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0;streak=maxstreak=0
    for x in p:
        eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
        if x<=0:streak+=1;maxstreak=max(maxstreak,streak)
        else:streak=0
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'median':statistics.median(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd,'max_loss_streak':maxstreak}

def block_bootstrap(T,iters=5000):
    by=defaultdict(list)
    for x in T:by[x['day']].append(x['pnl'])
    days=list(by); rng=random.Random(260108); means=[]
    for _ in range(iters):
        vals=[]
        for __ in days:
            d=rng.choice(days);vals.extend(by[d])
        means.append(sum(vals)/len(vals) if vals else 0)
    means.sort()
    return {'days':len(days),'mean_ci95':[means[int(.025*iters)],means[int(.975*iters)]],'prob_mean_positive':sum(x>0 for x in means)/iters}

def main():
    D={m:load(m) for m in MONTHS}; S={m:signals(D[m]) for m in MONTHS}
    result={'rule':'Frozen 2026 survivor #3: IPR(20,1.5 ATR,eff .50,pullback .40,retain .20,wait 5), SHORT only, 06-17 UTC, enter next minute, hold 10m, one position','costs':{}}
    for cost in (.26,.36,.46,.56,.76):
        allT=[];monthly={}
        for m in MONTHS:
            T=trades(D[m],S[m],cost);monthly[m]=stats(T);allT+=T
        result['costs'][str(cost)]={'aggregate':stats(allT),'monthly':monthly,'positive_months':sum(monthly[m]['sum']>0 for m in MONTHS),'bootstrap':block_bootstrap(allT)}
    OUT.joinpath('candidate_2025.json').write_text(json.dumps(result,indent=2))
    base=result['costs']['0.26'];stress=result['costs']['0.46']
    summary={'base':base['aggregate'],'base_positive_months':base['positive_months'],'base_bootstrap':base['bootstrap'],'stress46':stress['aggregate'],'stress46_positive_months':stress['positive_months'],'stress46_bootstrap':stress['bootstrap']}
    OUT.joinpath('candidate_2025_summary.md').write_text('# Frozen candidate 2025 validation\n\n'+json.dumps(summary,indent=2)+'\n\n## Monthly @ 0.26\n'+json.dumps(base['monthly'],indent=2))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
