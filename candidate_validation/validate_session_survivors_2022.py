#!/usr/bin/env python3
from __future__ import annotations
import csv,json,random,urllib.request
from collections import defaultdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2022_{month}.csv'
MONTHS=[f'{i:02d}' for i in range(1,13)]
OUT=Path('session_2022_output'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

RULES=[
 {'name':'retest_strict','buffer':0.3,'band':0.4,'wait':10},
 {'name':'retest_loose','buffer':0.0,'band':0.2,'wait':10},
]

def read(m,side):
    p=DATA/f'{side}_{m}.csv'
    if not p.exists(): urllib.request.urlretrieve(BASE.format(side=side,month=m),p)
    q={}
    with p.open() as f:
        for z in csv.DictReader(f):
            q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
    return q

def load(m):
    A,B=read(m,'ask'),read(m,'bid');b=[]
    for t in sorted(set(A)&set(B)):
        a,z=A[t],B[t]
        b.append({'t':t,'day':t//86400000,'hr':(t//3600000)%24,'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2})
    tr=[0.0]*len(b);atr=[0.0]*len(b);s=0
    for i in range(1,len(b)):
        tr[i]=max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    return b,atr

def entries(data,rule):
    b,a=data;days=defaultdict(list)
    for i,x in enumerate(b):days[x['day']].append(i)
    out=[]
    for idxs in days.values():
        R=[i for i in idxs if 6<=b[i]['hr']<12]; W=[i for i in idxs if 12<=b[i]['hr']<17]
        if len(R)<30 or not W:continue
        rl=min(b[i]['l'] for i in R);at=max(a[R[-1]],.05)
        br=None
        for wi,i in enumerate(W):
            if b[i]['c']<=rl-rule['buffer']*at:
                br=(wi,i,rl);break
        if not br:continue
        wi,ii,lv=br
        for j in W[wi+1:wi+1+rule['wait']]:
            if b[j]['h']>=lv-rule['band']*at and b[j]['c']<lv and b[j]['c']<b[j]['o'] and j+1<len(b):
                out.append(j+1);break
    return out

def trades(data,E,cost):
    b=data[0];out=[];busy=-1
    for e in E:
        if e<=busy or e+60>=len(b):continue
        pnl=(b[e]['o']-b[e+60]['o'])-cost
        out.append({'pnl':pnl,'day':b[e]['day']});busy=e+60
    return out

def stats(T):
    p=[x['pnl'] for x in T]
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0
    for x in p:
        eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def bootstrap(T,n=10000):
    by=defaultdict(list)
    for x in T:by[x['day']].append(x['pnl'])
    days=list(by);r=random.Random(20221008);means=[]
    for _ in range(n):
        z=[]
        for __ in days:z.extend(by[r.choice(days)])
        means.append(sum(z)/len(z) if z else 0)
    means.sort()
    return {'days':len(days),'ci95':[means[int(.025*n)],means[int(.975*n)]],'p_mean_positive':sum(x>0 for x in means)/n}

def main():
    D={m:load(m) for m in MONTHS};res=[]
    for rule in RULES:
        E={m:entries(D[m],rule) for m in MONTHS};rr={'rule':rule,'costs':{}}
        for cost in (.26,.36,.46,.56,.76,1.00):
            allT=[];monthly={}
            for m in MONTHS:
                T=trades(D[m],E[m],cost);monthly[m]=stats(T);allT.extend(T)
            rr['costs'][str(cost)]={'aggregate':stats(allT),'positive_months':sum(monthly[m]['sum']>0 for m in MONTHS),'monthly':monthly,'bootstrap':bootstrap(allT)}
        res.append(rr)
    OUT.joinpath('validation_2022.json').write_text(json.dumps(res,indent=2))
    brief=[]
    for r in res:
        brief.append({'rule':r['rule'],'base':r['costs']['0.26']['aggregate'],'base_positive_months':r['costs']['0.26']['positive_months'],'bootstrap':r['costs']['0.26']['bootstrap'],'cost46':r['costs']['0.46']['aggregate'],'cost76':r['costs']['0.76']['aggregate']})
    OUT.joinpath('summary.md').write_text('# Frozen session survivors — 2022 untouched validation\n\n'+json.dumps(brief,indent=2))
    print(json.dumps(brief,indent=2),flush=True)

if __name__=='__main__':main()
