"""Independent equation checks, missing-data cases and official-table regression."""
import json
from pathlib import Path
import numpy as np
from model import IOModel, emit

report={}
def near(a,b): np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-9)
def rejected(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')
def values(m,r):return np.array([next(s['change'] for s in r['rows'] if s['code']==c)/100 for c in m.codes])
# Analytically solvable two-sector model: A=[[.1,.2],[.3,.1]].
# Unit cost shock [.1,0] gives prices [0.12, .0266666666667].
book={'d':[['code','name','a','b','x','va'],['a','농업',10,20,100,55],['b','서비스',30,10,100,63]],'m':[['code','name','a','b'],['a','농업',4,5],['b','서비스',1,2]]}
p=dict(sheet='d',start='C2',n=2,codeStart='A2',nameStart='B2',output='E2',outputAxis='col',va='F2',vaAxis='col',importsSheet='m',importsStart='C2',basis='domestic',kind='transactions',year='2020',unit='million USD',level='custom')
m=IOModel(book=book,mapping=p)
m.extra['wage']=np.array([1.,0.]);r=m.price(dict(mode='cost',wage=10));near(values(m,r),[.12,.0266666666666667])
# External foreign price +10% and exchange rate +10% give +21% for a, +10% for b.
r=m.price(dict(mode='import',code='a',foreign=10,fx=10));near(values(m,r),np.linalg.solve(np.eye(2)-m.A.T,m.Am.T@np.array([.21,.1])))
near(values(m,m.price(dict(mode='fx',fx=-10))),np.linalg.solve(np.eye(2)-m.A.T,m.Am.T@np.array([-.1,-.1])))
# Fixed a price +10%: b=(.2*.1)/(.9), a stays .1 rather than being amplified.
r=m.price(dict(mode='product',code='a',product=10));near(values(m,r),[.1,.02/.9]);assert next(r for r in r['rows'] if r['code']=='a')['fixed']
rejected(lambda:m.price(dict(mode='product',code='all',product=10)))
rejected(lambda:m.price(dict(mode='fx',fx=-101)))
rejected(lambda:m.price(dict(mode='fx',fx='nan')))
rejected(lambda:m.price(dict(mode='cost',wage=0)))
rejected(lambda:m.price(dict(mode='invalid')))
e=m.economy({});assert e['rows'][0]['totalDemand'] is None and e['rows'][0]['finalDemandRate'] is None
m.extra['supplyTotal']=np.array([120.,130.]);m.extra['finalTotal']=np.array([81.,88.]);m._refresh_structure()
e=m.economy({});near(e['rows'][0]['intermediateDemand'],39);near(e['rows'][0]['finalDemandRate'],67.5)
l=m.learning(dict(supplier='a',buyer='b'));near(l['transaction'],20);near(l['coefficient'],.2);near(l['totalTransaction'],25)
assert l['grid']==[[10.,20.],[30.,10.]];emit(l);emit(e)
# Scale amounts without changing shares, coefficients or price effects.
scaled={k:[row[:] for row in rows] for k,rows in book.items()}
for rows in scaled.values():
 for row in rows[1:]:
  row[2:]=[v*100 for v in row[2:]]
ms=IOModel(book=scaled,mapping={**p,'unit':'USD'});near(ms.learning(dict(supplier='a',buyer='b'))['coefficient'],l['coefficient']);near(ms.economy({})['rows'][0]['outputShare'],50)
# Total table without import separation must not pretend to give domestic prices.
mt=IOModel(book=book,mapping={**p,'basis':'total','importsSheet':''});rejected(lambda:mt.price(dict(mode='product',code='a',product=10)));assert not mt.learning({})['domestic']
# Domestic coefficients without amounts permit price analysis, not amount-based structure.
coeff={'c':[['code','name','a','b'],['a','농업',.1,.2],['b','서비스',.3,.1]]}
mc=IOModel(book=coeff,mapping={**p,'sheet':'c','kind':'coefficients','importsSheet':'','output':'','va':''})
assert mc.economy({})['rows'][0]['outputShare'] is None;assert mc.learning({})['transaction'] is None
near(values(mc,mc.price(dict(mode='product',code='a',product=10))),[.1,.02/.9]);rejected(lambda:mc.price(dict(mode='fx',fx=10)))
# A one-sector model can be entirely exogenized.
one={'c':[['code','name','a'],['a','농업',.2]]}
mo=IOModel(book=one,mapping={**p,'sheet':'c','n':1,'kind':'coefficients','importsSheet':'','output':'','va':''})
near(mo.price(dict(mode='product',code='a',product=10))['rows'][0]['change'],10)
report['synthetic']='Analytical 2-sector costs; import/FX interaction; fixed-price elimination; missing-data, total basis, amount scaling, coefficient-only and 1-sector cases passed'
ref=json.loads(Path('data/reference-2023.json').read_text())
for level in ['large','medium','small','basic']:
 m=IOModel(Path('data/io-'+level+'.xlsx').read_bytes(),'한국은행 예시.xlsx')
 assert m.info()['ready'];e=m.economy({});near(sum(r['outputShare'] for r in e['rows']),100);near(sum(r['valueAddedShare'] for r in e['rows']),100)
 for row in e['rows']:
  if row['totalDemand']!=0:near(row['intermediateDemandRate']+row['finalDemandRate'],100)
 for mode,args in [('cost',{'wage':10}),('import',{'foreign':10,'fx':10}),('fx',{'fx':10}),('product',{'product':10})]:
  p={'mode':mode,'code':m.codes[0],**args};r=m.price(p);dp=values(m,r)
  if mode=='cost':rhs=np.zeros(m.n);rhs[0]=m.extra['wage'][0]*.1
  elif mode=='import':pm=np.full(m.n,.1);pm[0]=.21;rhs=m.Am.T@pm
  elif mode=='fx':rhs=m.Am.T@np.full(m.n,.1)
  else:
   near(dp[0],.1);near((np.eye(m.n)-m.A.T)[1:]@dp, np.zeros(m.n-1));continue
  near((np.eye(m.n)-m.A.T)@dp,rhs)
 m.attach_reference({'snapshot':ref['snapshots'][level],'benchmarks':ref['benchmarks']})
 v=m.validation_report();checks=v['rows']+v['benchmarks'];assert all(c['pass_'] for c in checks)
 for sheet in m.book:
  for axis in ['row','col']:assert m.explore({'sheet':sheet,'axis':axis})['cells']
 learning=m.learning({'supplier':m.codes[-1],'buyer':m.codes[-1]});emit(learning);emit(e)
 report[level]={'industries':m.n,'officialChecks':len(checks),'maxDemandBalanceResidual':max(abs(r['balanceResidual']) for r in e['rows']),'fourPriceModes':'passed','sheets':len(m.book)}
 print(level,report[level],flush=True)
Path('course-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('PASS course checks',flush=True)
