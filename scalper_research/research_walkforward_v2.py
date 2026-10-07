#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

BASE='https://raw.githubusercontent.com/3650326613-png/dukascopy_xauusd_1m_data/main/xauusd/{side}/m1/xauusd_{side}_m1_2026_{month}.csv'
MONTHS=['01','02','03','04','05','06','07','08']
DEV=['01','02','03','04','05']; VAL=['06','07']; HOLD=['08']
SESSIONS={'all':[(0,24)],'london_ny':[(6,17)],'us':[(12,22)],'ny_overlap':[(12,17)]}
OUT=Path('research_output_v2'); DATA=OUT/'data'; OUT.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

@dataclass(frozen=True)
class Setup:
    fam:str; p:tuple
@dataclass(frozen=True)
class Exit:
    kind:str; p:tuple
@dataclass
class Signal:
    entry:int; dir:int; px:float; atr:float; hour:int

def dl(m,side):
    p=DATA/f'{side}_{m}.csv'
    if not p.exists(): urllib.request.urlretrieve(BASE.format(side=side,month=m),p)
    return p

def read_side(p):
    out={}
    with p.open() as f:
        for z in csv.DictReader(f):
            out[int(z['timestamp'])]=(float(z['open']),float(z['high']),float(z['low']),float(z['close']))
    return out

def load(m):
    A=read_side(dl(m,'ask')); B=read_side(dl(m,'bid')); bars=[]
    for t in sorted(set(A)&set(B)):
        a,b=A[t],B[t]
        bars.append({'t':t,'o':(a[0]+b[0])/2,'h':(a[1]+b[1])/2,'l':(a[2]+b[2])/2,'c':(a[3]+b[3])/2,'hour':(t//3600000)%24})
    return bars

def prep(b):
    n=len(b); c=[x['c'] for x in b]; h=[x['h'] for x in b]; l=[x['l'] for x in b]
    tr=[0.0]*n
    for i in range(1,n): tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    atr=[0.0]*n; s=0.0; w=20
    for i,x in enumerate(tr):
        s+=x
        if i>=w:s-=tr[i-w]
        atr[i]=s/min(i+1,w)
    return c,h,l,atr

def sgn(x):return 1 if x>0 else -1 if x<0 else 0

def eff(c,i,w):
    p=sum(abs(c[k]-c[k-1]) for k in range(i-w+1,i+1)); return abs(c[i]-c[i-w])/(p+1e-12)

def ext(h,l,i,w):return max(h[i-w:i]),min(l[i-w:i])

def z(c,i,w):
    a=c[i-w+1:i+1]; mu=sum(a)/w; sd=statistics.pstdev(a); return 0 if sd<1e-12 else (c[i]-mu)/sd

def setups():
    q=[]
    for n in (10,20,30):
      for k in (1.5,2.5,3.5):
       for ef in (.5,.7):
        for pb in (.4,.6):
         for ret in (.2,.4):
          for wait in (3,5):q.append(Setup('ipr',(n,k,ef,pb,ret,wait)))
    for n in (10,20,60):
     for ov in (.2,.5,.8):
      for wick in (.5,.7):
       for rec in (0,.2):q.append(Setup('sweep',(n,ov,wick,rec)))
    for n in (10,20,60):
     for bo in (0,.25,.5):
      for band in (.2,.5):
       for inv in (.5,1.0):
        for wait in (3,5):q.append(Setup('brt',(n,bo,band,inv,wait)))
    for sw in (5,10):
     for lw in (30,60):
      for cr in (.3,.5):
       for ex in (1.2,1.8):q.append(Setup('compress',(sw,lw,cr,ex)))
    for w in (20,60):
     for zz in (1.5,2,2.5):
      for me in (.3,.5):q.append(Setup('mr',(w,zz,me)))
    for w in (20,30,60):
     for k in (1.5,2.5,3.5):
      for ef in (.4,.6):
       for pb in (1,2):q.append(Setup('trend',(w,k,ef,pb)))
    return q

def signals(b,s):
    c,h,l,a=prep(b); N=len(b); out=[]; fam=s.fam; p=s.p
    if fam=='ipr':
        w,k,me,pb,ret,wait=p
        for i in range(max(65,w+2),N-8):
            mv=c[i]-c[i-w]; d=sgn(mv); atr=max(a[i],.05)
            if not d or abs(mv)<k*atr or eff(c,i,w)<me:continue
            base,peak=c[i-w],c[i]; r=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if d*(peak-c[j])>=pb*abs(mv) and d*(c[j]-base)>=ret*abs(mv):r=j;break
            if r<0:continue
            j=r+1
            if sgn(c[j]-c[j-1])==d and d*(c[j]-base)>=ret*abs(mv):out.append(Signal(j+1,d,b[j+1]['o'],a[j],b[j+1]['hour']))
    elif fam=='sweep':
        w,ov,wick,rec=p
        for i in range(max(65,w),N-2):
            ph,pl=ext(h,l,i,w); atr=max(a[i],.05); rng=h[i]-l[i]
            if rng<=0:continue
            if h[i]-ph>=ov*atr and c[i]<=ph-rec*atr and (h[i]-c[i])/rng>=wick:out.append(Signal(i+1,-1,b[i+1]['o'],atr,b[i+1]['hour']))
            elif pl-l[i]>=ov*atr and c[i]>=pl+rec*atr and (c[i]-l[i])/rng>=wick:out.append(Signal(i+1,1,b[i+1]['o'],atr,b[i+1]['hour']))
    elif fam=='brt':
        w,bo,band,inv,wait=p
        for i in range(max(65,w),N-8):
            ph,pl=ext(h,l,i,w); atr=max(a[i],.05); d=0;level=0
            if c[i]>=ph+bo*atr:d=1;level=ph
            elif c[i]<=pl-bo*atr:d=-1;level=pl
            else:continue
            r=-1
            for j in range(i+1,min(N-2,i+wait+1)):
                if d==1 and l[j]<=level+band*atr and c[j]>=level-inv*atr:r=j;break
                if d==-1 and h[j]>=level-band*atr and c[j]<=level+inv*atr:r=j;break
            if r>=0 and ((d==1 and c[r]>level and c[r]>b[r]['o']) or (d==-1 and c[r]<level and c[r]<b[r]['o'])):out.append(Signal(r+1,d,b[r+1]['o'],atr,b[r+1]['hour']))
    elif fam=='compress':
        sw,lw,cr,ex=p
        for i in range(max(65,lw),N-2):
            sr=max(h[i-sw:i])-min(l[i-sw:i]); lr=max(h[i-lw:i])-min(l[i-lw:i]); atr=max(a[i],.05)
            if lr<=0 or sr/lr>cr or h[i]-l[i]<ex*atr:continue
            ph,pl=ext(h,l,i,sw)
            if c[i]>ph:out.append(Signal(i+1,1,b[i+1]['o'],atr,b[i+1]['hour']))
            elif c[i]<pl:out.append(Signal(i+1,-1,b[i+1]['o'],atr,b[i+1]['hour']))
    elif fam=='mr':
        w,zt,me=p
        for i in range(max(65,w),N-2):
            zz=z(c,i,w); d=-sgn(zz)
            if d and abs(zz)>=zt and eff(c,i,min(20,w))<=me and sgn(c[i]-c[i-1])==d:out.append(Signal(i+1,d,b[i+1]['o'],a[i],b[i+1]['hour']))
    else:
        w,k,me,pbn=p
        for i in range(max(65,w+pbn),N-2):
            mv=c[i]-c[i-w]; d=sgn(mv); atr=max(a[i],.05)
            if not d or abs(mv)<k*atr or eff(c,i,w)<me:continue
            if all(d*(c[j]-c[j-1])<=0 for j in range(i-pbn,i)) and d*(c[i]-c[i-1])>0:out.append(Signal(i+1,d,b[i+1]['o'],atr,b[i+1]['hour']))
    return out

def sess_ok(h,s):return any(a<=h<b for a,b in SESSIONS[s])

def stats(p):
    if not p:return {'n':0,'sum':0,'mean':0,'pf':0,'win':0,'mdd':0}
    gp=sum(x for x in p if x>0);gl=-sum(x for x in p if x<=0);eq=pk=dd=0
    for x in p:eq+=x;pk=max(pk,eq);dd=max(dd,pk-eq)
    return {'n':len(p),'sum':sum(p),'mean':sum(p)/len(p),'pf':gp/gl if gl else 99,'win':sum(x>0 for x in p)/len(p),'mdd':dd}

def sim(b,sigs,ex,session='all',direction=0,cost=.26):
    P=[];busy=-1
    for x in sigs:
        if x.entry<=busy or not sess_ok(x.hour,session) or (direction and x.dir!=direction):continue
        if ex.kind=='hold':
            end=x.entry+ex.p[0]
            if end>=len(b):break
            gross=x.dir*(b[end]['o']-x.px);busy=end
        else:
            tpM,slM,mh=ex.p;tp=max(.05,tpM*x.atr);sl=max(.05,slM*x.atr);last=min(len(b)-1,x.entry+mh);gross=None;busy=last
            for j in range(x.entry,last+1):
                ht=(b[j]['h']>=x.px+tp if x.dir==1 else b[j]['l']<=x.px-tp)
                hs=(b[j]['l']<=x.px-sl if x.dir==1 else b[j]['h']>=x.px+sl)
                if ht and hs:gross=-sl;busy=j;break
                if hs:gross=-sl;busy=j;break
                if ht:gross=tp;busy=j;break
            if gross is None:gross=x.dir*(b[last]['c']-x.px)
        P.append(gross-cost)
    return P

def agg(months,bars,S,ex,session='all',direction=0,cost=.26):
    allp=[];mon={}
    for m in months:
        p=sim(bars[m],S[m],ex,session,direction,cost);mon[m]=stats(p);allp.extend(p)
    return stats(allp),mon

def main():
    bars={m:load(m) for m in MONTHS}; Q=setups();print('bars',{m:len(v) for m,v in bars.items()},'setups',len(Q),flush=True)
    screen=[];dev_sigs={}
    for i,s in enumerate(Q):
        S={m:signals(bars[m],s) for m in DEV};dev_sigs[i]=S
        for hold in (5,10,20):
            ex=Exit('hold',(hold,))
            for sess in ('all','london_ny','us'):
                st,mon=agg(DEV,bars,S,ex,sess,0,.26); st36,_=agg(DEV,bars,S,ex,sess,0,.36)
                pos=sum(mon[m]['sum']>0 for m in DEV)
                if st['n']>=60 and st['sum']>0 and st['pf']>1.03 and pos>=3 and st36['sum']>0:
                    score=(st['pf']-1)*math.sqrt(st['n'])*max(st['mean'],.001)*(1+pos/5)/(1+st['mdd']/max(st['sum'],1))
                    screen.append((score,i,hold,sess,st))
        if (i+1)%50==0:print('screened',i+1,flush=True)
    screen.sort(reverse=True,key=lambda x:x[0])
    shortlist=[]
    for row in screen:
        if row[1] not in shortlist:shortlist.append(row[1])
        if len(shortlist)>=60:break
    print('screen viable',len(screen),'unique shortlist',len(shortlist),flush=True)
    exits=[Exit('hold',(h,)) for h in (3,5,10,15,20,30)]
    for tp in (.75,1,1.25,1.5,2):
      for sl in (.5,.75,1,1.25):
       for mh in (5,10,20):exits.append(Exit('bracket',(tp,sl,mh)))
    detailed=[]
    for i in shortlist:
        S=dev_sigs[i]
        for ex in exits:
          for sess in SESSIONS:
           for direc in (0,1,-1):
            st,mon=agg(DEV,bars,S,ex,sess,direc,.26)
            if st['n']<45 or st['sum']<=0 or st['pf']<=1.05:continue
            pos=sum(mon[m]['sum']>0 for m in DEV)
            if pos<3:continue
            st36,_=agg(DEV,bars,S,ex,sess,direc,.36)
            if st36['sum']<=0:continue
            score=(st['pf']-1)*math.sqrt(st['n'])*st['mean']*(1+pos/5)/(1+st['mdd']/max(st['sum'],1))
            detailed.append((score,i,ex,sess,direc,st,mon,st36))
    detailed.sort(reverse=True,key=lambda x:x[0]);top=detailed[:200]
    print('detailed dev viable',len(detailed),'top',len(top),flush=True)
    need=sorted({r[1] for r in top});val_sigs={i:{m:signals(bars[m],Q[i]) for m in VAL} for i in need}
    validated=[]
    for row in top:
        score,i,ex,sess,direc,dst,dmon,d36=row
        vst,vmon=agg(VAL,bars,val_sigs[i],ex,sess,direc,.26);v36,_=agg(VAL,bars,val_sigs[i],ex,sess,direc,.36)
        if vst['n']>=18 and vst['sum']>0 and vst['pf']>1.03 and v36['sum']>=0:
            vpos=sum(vmon[m]['sum']>0 for m in VAL)
            vs=(vst['pf']-1)*math.sqrt(vst['n'])*vst['mean']*(1+vpos/2)/(1+vst['mdd']/max(vst['sum'],1))
            validated.append((vs,row,vst,vmon,v36))
    validated.sort(reverse=True,key=lambda x:x[0]);frozen=validated[:25]
    print('validated',len(validated),'frozen',len(frozen),flush=True)
    needH=sorted({x[1][1] for x in frozen});hold_sigs={i:{m:signals(bars[m],Q[i]) for m in HOLD} for i in needH}
    results=[]
    for vs,row,vst,vmon,v36 in frozen:
        score,i,ex,sess,direc,dst,dmon,d36=row
        h,hmon=agg(HOLD,bars,hold_sigs[i],ex,sess,direc,.26);h36,_=agg(HOLD,bars,hold_sigs[i],ex,sess,direc,.36);h46,_=agg(HOLD,bars,hold_sigs[i],ex,sess,direc,.46)
        results.append({'setup':asdict(Q[i]),'exit':asdict(ex),'session':sess,'direction':direc,'dev':dst,'dev_monthly':dmon,'dev_cost36':d36,'val':vst,'val_monthly':vmon,'val_cost36':v36,'hold':h,'hold_cost36':h36,'hold_cost46':h46})
    survivors=[r for r in results if r['hold']['n']>=8 and r['hold']['sum']>0 and r['hold']['pf']>1.03 and r['hold_cost36']['sum']>=0]
    survivors.sort(key=lambda r:(r['hold_cost36']['sum'],r['hold']['pf'],r['hold']['mean']),reverse=True)
    payload={'method':{'dev':'Jan-May','validation':'Jun-Jul','holdout':'Aug','costs':[.26,.36,.46],'one_position':True,'same_bar_tp_sl':'SL-first'},'counts':{'setups':len(Q),'screen_viable':len(screen),'shortlist':len(shortlist),'detailed_dev_viable':len(detailed),'validated':len(validated),'frozen':len(frozen),'survivors':len(survivors)},'survivors':survivors,'frozen':results}
    (OUT/'results.json').write_text(json.dumps(payload,indent=2))
    with (OUT/'summary.md').open('w') as f:
        f.write('# XAUUSD staged walk-forward v2\n\n'+json.dumps(payload['counts'],indent=2)+'\n\n')
        for n,r in enumerate(survivors[:15],1):
            f.write(f"## Survivor {n}\n{r['setup']}\n{r['exit']} session={r['session']} direction={r['direction']}\n\n")
            for k in ('dev','val','hold','hold_cost36','hold_cost46'):f.write(f"- {k}: {r[k]}\n")
    print(json.dumps({'counts':payload['counts'],'top':survivors[:5]},indent=2),flush=True)

if __name__=='__main__':main()
