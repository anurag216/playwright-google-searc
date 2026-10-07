#!/usr/bin/env python3
from __future__ import annotations
import csv, json, random, statistics, urllib.request
from pathlib import Path
from collections import defaultdict

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2025_{month}.csv'
MONTHS=[f'{i:02d}' for i in range(1,13)]
OUT=Path('v2_survivor_2025'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

def read(m,side):
    p=DATA/f'{side}_{m}.csv'
    if not p.exists():urllib.request.urlretrieve(BASE.format(side=side,month=m),p)
    q={}
    with p.open() as f:
        for z in csv.DictReader(f):q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
    return q

def load(m):
    A,B=read(m,'ask'),read(m,'bid');b=[]
    for t in sorted(set(A)&set(B)):
        a,z=A[t],B[t];b.append({'t':t,'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2,'hr':(t//3600000)%24,'day':t//86400000})
    c=[x['c'] for x in b];h=[x['h'] for x in b];l=[x['l'] for x in b];tr=[0]*len(b);atr=[0]*len(b);s=0
    for i in range(1,len(b)):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    return b,c,h,l,atr

def eff(c,i,w):
    p=sum(abs(c[k]-c[k-1]) for k in range(i-w+1,i+1));return abs(c[i]-c[i-w])/(p+1e-12)

def ipr(data):
    b,c,h,l,a=data;o=[];N=len(b)
    for i in range(65,N-8):
        mv=c[i]-c[i-10]
        if mv>=0 or abs(mv)<3.5*max(a[i],.05) or eff(c,i,10)<.5:continue
        base,peak=c[i-10],c[i];r=-1
        for j in range(i+1,min(N-2,i+6)):
            if -(peak-c[j])>=.4*abs(mv) and -(c[j]-base)>=.4*abs(mv):r=j;break
        if r>=0:
            j=r+1
            if c[j]<c[j-1] and -(c[j]-base)>=.4*abs(mv):
                e=j+1
                if 12<=b[e]['hr']<17:o.append(e)
    return o

def brt(data):
    b,c,h,l,a=data;o=[];N=len(b)
    for i in range(65,N-8):
        ph=max(h[i-20:i]);pl=min(l[i-20:i]);at=max(a[i],.05)
        if c[i]<=pl-.5*at:d=-1;lv=pl
        else:continue
        r=-1
        for j in range(i+1,min(N-2,i+4)):
            if h[j]>=lv-.2*at and c[j]<=lv+.5*at:r=j;break
        if r>=0 and c[r]<lv and c[r]<b[r]['o']:
            e=r+1
            if 12<=b[e]['hr']<22:o.append(e)
    return o

def trades(data,entries,hold,cost):
    b=data[0];T=[];busy=-1
    for e in entries:
        if e<=busy or e+hold>=len(b):continue
        pnl=(b[e]['o']-b[e+hold]['o'])-cost
        T.append({'pnl':pnl,'day':b[e]['day']});busy=e+hold
    return T

def stat(T):
    p=[x['pnl'] for x in T]
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0
    for x in p:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def boot(T,n=5000):
    by=defaultdict(list)
    for x in T:by[x['day']].append(x['pnl'])
    days=list(by);rng=random.Random(2026);a=[]
    for _ in range(n):
        z=[]
        for __ in days:z+=by[rng.choice(days)]
        a.append(sum(z)/len(z) if z else 0)
    a.sort();return {'days':len(days),'ci95':[a[int(.025*n)],a[int(.975*n)]],'p_positive':sum(x>0 for x in a)/n}

def evaluate(name,gen,hold,D):
    E={m:gen(D[m]) for m in MONTHS};out={'name':name,'hold':hold,'costs':{}}
    for cost in (.26,.36,.46,.56):
        allT=[];mon={}
        for m in MONTHS:
            T=trades(D[m],E[m],hold,cost);mon[m]=stat(T);allT+=T
        out['costs'][str(cost)]={'aggregate':stat(allT),'positive_months':sum(mon[m]['sum']>0 for m in MONTHS),'monthly':mon,'bootstrap':boot(allT)}
    return out

def main():
    D={m:load(m) for m in MONTHS}
    R=[evaluate('IPR10_strict_NY_short_hold10',ipr,10,D),evaluate('BRT20_US_short_hold30',brt,30,D)]
    OUT.joinpath('validation.json').write_text(json.dumps(R,indent=2))
    brief=[]
    for r in R:
        brief.append({'name':r['name'],'base':r['costs']['0.26']['aggregate'],'base_positive_months':r['costs']['0.26']['positive_months'],'base_bootstrap':r['costs']['0.26']['bootstrap'],'cost46':r['costs']['0.46']['aggregate'],'cost46_positive_months':r['costs']['0.46']['positive_months']})
    OUT.joinpath('summary.md').write_text('# 2025 validation of v2 survivors\n\n'+json.dumps(brief,indent=2))
    print(json.dumps(brief,indent=2),flush=True)

if __name__=='__main__':main()
