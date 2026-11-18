"""SDA numerical invariants and actual workbook integration checks."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import decomposition as d
from model import IOModel, dispatch

def calc(periods,**kwargs):return d.compare(dict(periods=periods,basis='real',baseYear='2015',confirmed=True,**kwargs))
def near(a,b):np.testing.assert_allclose(a,b,rtol=1e-9,atol=1e-8)
def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')
p=d.demo();r=calc(p)
for m in r['methods'].values():near(m['residual'],0);near(np.sum(m['parts'],axis=1),r['change'])
# Independent equations for five isolated factor changes, plus combined changes.
a0=np.array([[.2,.1],[.1,.25]]);s0=np.array([[.1,.2],[.25,.1]]);m0=np.array([.2,.15]);f0=np.array([100.,120.]);e0=np.array([15.,35.])
def make(a,s,m,f,e,year):
 ad=a*(1-s);x=np.linalg.solve(np.eye(2)-ad,(1-m)*f+e)
 return dict(codes=['a','b'],names=['A','B'],meta=dict(year=str(year),price='생산자가격',unit='백만원',level='test'),x=x.tolist(),zd=(ad*x).tolist(),zm=(a*s*x).tolist(),f=f.tolist(),mf=(m*f).tolist(),e=e.tolist())
base=make(a0,s0,m0,f0,e0,2015)
for k in range(5):
 a,s,m,f,e=[v.copy() for v in [a0,s0,m0,f0,e0]]
 if k==0:f+=10
 if k==1:e+=10
 if k==2:m-=.03
 if k==3:s-=.03
 if k==4:a+=.01
 r1=calc([base,make(a,s,m,f,e,2020)])
 for result in r1['methods'].values():
  near(np.delete(np.array(result['parts']),k,axis=1),0);near(np.array(result['parts'])[:,k],r1['change'])
# Identical economics has zero change; no finite/infinite percentage division.
ident=deepcopy(p);ident[1]=deepcopy(ident[0]);ident[1]['meta']['year']='2020'
for v in calc(ident)['methods'].values():near(v['parts'],0)
# Code order alignment cannot change results.
shuffled=deepcopy(p);order=[2,0,1]
for key in ['codes','names','x','f','mf','e']:shuffled[1][key]=[p[1][key][i] for i in order]
for key in ['zd','zm']:shuffled[1][key]=np.array(p[1][key])[np.ix_(order,order)].tolist()
near(calc(shuffled)['methods']['paasche']['parts'],r['methods']['paasche']['parts'])
# Residual follows the independent accounting-residual identity for each path.
unbalanced=deepcopy(p);unbalanced[1]['f'][0]+=7
ur=calc(unbalanced)
for k,index in [('paasche',1),('laspeyres',0)]:
 balance=[]
 for snap in unbalanced:
  balance.append(np.array(snap['x'])-np.array(snap['zd']).sum(1)-np.array(snap['f'])+np.array(snap['mf'])-np.array(snap['e']))
 snap=unbalanced[index];L=np.linalg.inv(np.eye(3)-np.array(snap['zd'])/np.array(snap['x']))
 near(ur['methods'][k]['residual'],L@(balance[1]-balance[0]))
for field,value in [('unit','USD'),('price','기초가격'),('level','other'),('year','2015')]:
 bad=deepcopy(p);bad[1]['meta'][field]=value;reject(lambda:calc(bad))
bad=deepcopy(p);bad[1]['names'][0]='different';reject(lambda:calc(bad))
bad=deepcopy(p);bad[1]['x'][0]=float('nan');reject(lambda:calc(bad))
reject(lambda:d.compare(dict(periods=p,basis='real',baseYear='',confirmed=True)))
reject(lambda:d.compare(dict(periods=p,basis='nominal',confirmed=False)))
# Undefined share convention at emergence of a formerly zero intermediate flow.
z0=a0.copy();z0[0,1]=0
zr=calc([make(z0,s0,m0,f0,e0,2015),make(a0,s0,m0,f0,e0,2020)])
assert zr['zeroConventions']>0
near(zr['methods']['paasche']['residual'],0)
assert json.loads(dispatch('sda_demo','{}'))[0]['demo']
report={'synthetic':'Five isolated drivers; exact sum; identical economy; order alignment; residual identity; invalid inputs; zero denominators; no-data worker dispatch passed','workbooks':{}}
for level in ['large','medium','small','basic']:
 model=IOModel(Path('data/io-'+level+'.xlsx').read_bytes(),'한국은행 예시.xlsx');snap=d.snapshot(model)
 other=deepcopy(snap);other['meta']['year']='2024'
 result=calc([snap,other]);near(result['change'],0)
 for method in result['methods'].values():near(method['parts'],0)
 report['workbooks'][level]={'industries':len(snap['codes']),'maximumAccountingResidual':result['balanceMax'][0],'relativeAccountingResidual':result['balanceRelative'][0],'snapshotAndIdenticalEconomy':'passed; second year relabeled only for regression, not real data'}
Path('decomposition-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
