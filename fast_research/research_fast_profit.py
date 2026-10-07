#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2026_{month}.csv'
DEV=['01','02','03','04','05']; VAL=['06','07']; HOLD=['08']; ALL=DEV+VAL+HOLD
SESS={'all':(0,24),'london_ny':(6,17),'us':(12,22),'ny_overlap':(12,17)}
OUT=Path('fast_output'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup: fam:str; p:tuple
@dataclass(frozen=True)
class Exit: kind:str; p:tuple
@dataclass
class Sig: i:int; d:int; px:float; atr:float; hr:int

def get(m,side):
    p=DATA/f'{side}_{m}.csv'
    if not p.exists(): urllib.request.urlretrieve(BASE.format(side=side,month=m),p)
    q={}
    with p.open() as f:
        for z in csv.DictReader(f): q[int(z['timestamp'])]=tuple(float(z[k]) for k in ('open','high','low','close'))
    return q

def load(m):
    A,B=get(m,'ask'),get(m,'bid'); b=[]
    for t in sorted(set(A)&set(B)):
        a,z=A[t],B[t]; b.append({'o':(a[0]+z[0])/2,'h':(a[1]+z[1])/2,'l':(a[2]+z[2])/2,'c':(a[3]+z[3])/2,'hr':(t//3600000)%24})
    c=[x['c'] for x in b];h=[x['h'] for x in b];l=[x['l'] for x in b];tr=[0]*len(b);atr=[0]*len(b);s=0
    for i in range(1,len(b)):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    for i,x in enumerate(tr):
        s+=x
        if i>=20:s-=tr[i-20]
        atr[i]=s/min(i+1,20)
    return b,c,h,l,atr

def sgn(x):return 1 if x>0 else -1 if x<0 else 0

def eff(c,i,w):
    p=0
    for k in range(i-w+1,i+1):p+=abs(c[k]-c[k-1])
    return abs(c[i]-c[i-w])/(p+1e-12)

def ext(h,l,i,w):return max(h[i-w:i]),min(l[i-w:i])

def configs():
    q=[]
    for n in (10,20,30):
      for k in (1.5,2.5):
       for e in (.5,.7):
        for pb in (.4,.6):
         for wait in (3,5):q.append(Setup('ipr',(n,k,e,pb,.2,wait)))
    for n in (10,20,60):
     for ov in (.3,.6):
      for wick in (.6,.75):q.append(Setup('sweep',(n,ov,wick,.1)))
    for n in (10,20,60):
     for bo in (0,.3):
      for wait in (3,5):q.append(Setup('brt',(n,bo,.3,.6,wait)))
    return q

def gen(d,s):
    b,c,h,l,a=d;N=len(b);o=[];f=s.fam;p=s.p
    if f=='ipr':
        w,k,ee,pb,ret,wait=p
        for i in range(max(65,w+2),N-8):
            mv=c[i]-c[i-w];dd=sgn(mv);at=max(a[i],.05)
            if not dd or abs(mv)<k*at or eff(c,i,w)<ee:continue
            base,peak=c[i-w],c[i];r=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if dd*(peak-c[j])>=pb*abs(mv) and dd*(c[j]-base)>=ret*abs(mv):r=j;break
            if r>=0:
                j=r+1
                if sgn(c[j]-c[j-1])==dd and dd*(c[j]-base)>=ret*abs(mv):o.append(Sig(j+1,dd,b[j+1]['o'],a[j],b[j+1]['hr']))
    elif f=='sweep':
        w,ov,wick,rec=p
        for i in range(max(65,w),N-2):
            ph,pl=ext(h,l,i,w);at=max(a[i],.05);rg=h[i]-l[i]
            if rg<=0:continue
            if h[i]-ph>=ov*at and c[i]<=ph-rec*at and (h[i]-c[i])/rg>=wick:o.append(Sig(i+1,-1,b[i+1]['o'],at,b[i+1]['hr']))
            elif pl-l[i]>=ov*at and c[i]>=pl+rec*at and (c[i]-l[i])/rg>=wick:o.append(Sig(i+1,1,b[i+1]['o'],at,b[i+1]['hr']))
    else:
        w,bo,band,inv,wait=p
        for i in range(max(65,w),N-8):
            ph,pl=ext(h,l,i,w);at=max(a[i],.05);dd=0;lv=0
            if c[i]>=ph+bo*at:dd=1;lv=ph
            elif c[i]<=pl-bo*at:dd=-1;lv=pl
            else:continue
            r=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if dd==1 and l[j]<=lv+band*at and c[j]>=lv-inv*at:r=j;break
                if dd==-1 and h[j]>=lv-band*at and c[j]<=lv+inv*at:r=j;break
            if r>=0 and ((dd==1 and c[r]>lv and c[r]>b[r]['o']) or (dd==-1 and c[r]<lv and c[r]<b[r]['o'])):o.append(Sig(r+1,dd,b[r+1]['o'],at,b[r+1]['hr']))
    return o

def exits():
    x=[Exit('hold',(h,)) for h in (5,10,20)]
    for tp in (1,1.5,2):
     for sl in (.75,1,1.25):
      for mh in (5,10,20):x.append(Exit('bracket',(tp,sl,mh)))
    return x

def stat(p):
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0
    for x in p:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def sim(data,S,ex,sess,direction,cost):
    b=data[0];P=[];busy=-1;lohr,hihr=SESS[sess]
    for x in S:
        if x.i<=busy or not(lohr<=x.hr<hihr) or (direction and x.d!=direction):continue
        if ex.kind=='hold':
            e=x.i+ex.p[0]
            if e>=len(b):break
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

def agg(months,D,S,ex,se,di,cost):
    P=[];M={}
    for m in months:
        p=sim(D[m],S[m],ex,se,di,cost);M[m]=stat(p);P+=p
    return stat(P),M

def main():
    D={m:load(m) for m in ALL};Q=configs();E=exits()
    print('loaded', {m:len(D[m][0]) for m in ALL}, 'setups',len(Q),'exits',len(E),flush=True)
    dev=[]
    for qi,q in enumerate(Q):
        S={m:gen(D[m],q) for m in DEV}
        for ex in E:
          for se in SESS:
           for di in (0,1,-1):
            st,mon=agg(DEV,D,S,ex,se,di,.26)
            if st['n']<45 or st['sum']<=0 or st['pf']<=1.05 or sum(mon[m]['sum']>0 for m in DEV)<3:continue
            x36,_=agg(DEV,D,S,ex,se,di,.36)
            if x36['sum']<=0:continue
            score=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1))
            dev.append((score,qi,ex,se,di,st,mon,x36))
    dev.sort(reverse=True,key=lambda x:x[0]);dev=dev[:100]
    print('dev finalists',len(dev),flush=True)
    ids={x[1] for x in dev};SV={i:{m:gen(D[m],Q[i]) for m in VAL} for i in ids};val=[]
    for r in dev:
        sc,i,ex,se,di,dst,dmon,d36=r;st,mon=agg(VAL,D,SV[i],ex,se,di,.26);x36,_=agg(VAL,D,SV[i],ex,se,di,.36)
        if st['n']>=15 and st['sum']>0 and st['pf']>1.03 and x36['sum']>=0:
            vs=(st['pf']-1)*math.sqrt(st['n'])*st['mean']/(1+st['mdd']/max(st['sum'],1));val.append((vs,r,st,mon,x36))
    val.sort(reverse=True,key=lambda x:x[0]);val=val[:20]
    print('validation finalists',len(val),flush=True)
    ids={x[1][1] for x in val};SH={i:{'08':gen(D['08'],Q[i])} for i in ids};res=[]
    for vs,r,vst,vmon,v36 in val:
        sc,i,ex,se,di,dst,dmon,d36=r;h,hm=agg(HOLD,D,SH[i],ex,se,di,.26);h36,_=agg(HOLD,D,SH[i],ex,se,di,.36);h46,_=agg(HOLD,D,SH[i],ex,se,di,.46)
        res.append({'setup':asdict(Q[i]),'exit':asdict(ex),'session':se,'direction':di,'dev':dst,'dev_monthly':dmon,'val':vst,'val_monthly':vmon,'hold':h,'hold36':h36,'hold46':h46})
    surv=[r for r in res if r['hold']['n']>=6 and r['hold']['sum']>0 and r['hold']['pf']>1.03 and r['hold36']['sum']>=0]
    surv.sort(key=lambda r:(r['hold36']['sum'],r['hold']['pf']),reverse=True)
    out={'counts':{'setups':len(Q),'dev_finalists':len(dev),'val_finalists':len(val),'survivors':len(surv)},'survivors':surv,'frozen':res}
    (OUT/'fast_results.json').write_text(json.dumps(out,indent=2))
    (OUT/'fast_summary.md').write_text('# Fast profit search\n\n'+json.dumps(out['counts'],indent=2)+'\n\n'+json.dumps(surv[:10],indent=2))
    print(json.dumps({'counts':out['counts'],'top':surv[:5]},indent=2),flush=True)

if __name__=='__main__':main()
