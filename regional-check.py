"""Run: OPENBLAS_NUM_THREADS=1 python regional-check.py; optional --template."""
import copy,io,json,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment
import regional as r
checks=[]
def check(name,fn):
    fn();checks.append(name)
def close(a,b):np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-9)
def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')
def workbook(p):
    w=openpyxl.Workbook();w.remove(w.active)
    ws=w.create_sheet('metadata');ws.append(['key','value'])
    for k,v in {**p['meta'],'data_type':'synthetic' if p.get('demo') else 'observed'}.items():ws.append([k,v])
    keys=['code','region','industry','name','output','value_added','imports','employment'];ws=w.create_sheet('nodes');ws.append(keys)
    for node in p['nodes']:ws.append([node.get(k) for k in keys])
    codes=[n['code'] for n in p['nodes']];ws=w.create_sheet('transactions');ws.append(['code']+codes)
    for code,row in zip(codes,p['Z']):ws.append([code]+row)
    if p.get('F') is not None:
        ws=w.create_sheet('final_demand');ws.append(['code']+list(dict.fromkeys(n['region'] for n in p['nodes']))+['exports'])
        for code,row,e in zip(codes,p['F'],p['exports']):ws.append([code]+row+[e])
    return w
def raw(w):
    b=io.BytesIO();w.save(b);return b.getvalue()
p=r.demo_data();m=r.RegionalModel(p)
check('balanced demo inputs',lambda:close(m.input_error,0))
check('balanced demo outputs',lambda:close(m.output_error,0))
s=m.simulate(dict(region=m.regions[0],industry='B',amount=100))
f=np.zeros(9);f[1]=100
check('scenario independent linear solve',lambda:close([x['production'] for x in s['rows']],np.linalg.solve(np.eye(9)-m.A,f)))
check('own other and feedback identities',lambda:close([s['own']+s['other'],s['isolated']+s['feedback']],[s['production'],s['own']]))
check('VA plus imported intermediates equals demand',lambda:close(s['valueAdded']+s['imports'],100))
check('employment direct coefficient identity',lambda:close(s['employment'],np.sum(m.e*(m.L@f))))
info=m.info()
check('LQ regional output weighted mean equals one',lambda:close([sum(o['lq']*next(g['outputShare']/100 for g in info['groups'] if g['region']==o['region']) for o in info['rows'] if o['industry']==k) for k in m.industries],np.ones(3)))
check('within-region industry shares sum 100',lambda:close([sum(o['withinShare'] for o in info['rows'] if o['region']==g) for g in m.regions],[100]*3))
check('VA destination orientation',lambda:close(info['vaFlows'],np.vstack([(m.v[:,None]*np.linalg.solve(np.eye(9)-m.A,m.F))[ix].sum(0) for ix in m.indices.values()])))
flows=np.array(info['vaFlows']);check('regional net VA flows sum zero',lambda:close((flows.sum(1)-flows.sum(0)).sum(),0))
q=dict(meta=p['meta'],nodes=[dict(code=str(i),region='R'+str(i),industry='A',name='A',output=100) for i in range(2)],Z=[[20,10],[30,40]])
t=r.RegionalModel(q);ss=t.simulate(dict(region='R0',industry='A',amount=10))
check('analytical two-region inverse',lambda:close(t.L,np.array([[.6,.1],[.3,.8]])/.45))
check('analytical feedback',lambda:close([ss['own'],ss['other'],ss['isolated'],ss['feedback']],[40/3,20/3,12.5,5/6]))
check('missing optional columns remain unavailable',lambda:close([ss[k] is None for k in ['valueAdded','imports','employment']],[True]*3))
qq=copy.deepcopy(q);qq['Z']=[[20,0],[0,40]];tt=r.RegionalModel(qq).simulate(dict(region='R0',industry='A',amount=10))
check('isolated regions have zero spillover and feedback',lambda:close([tt['other'],tt['feedback']],[0,0]))
neg=m.simulate(dict(region=m.regions[0],industry='B',amount=-10));check('small negative shocks are linear',lambda:close(neg['production'],-s['production']/10))
check('reject decline beyond existing production',lambda:reject(lambda:m.simulate(dict(region=m.regions[0],industry='B',amount=-100000))))
check('reject zero or nonfinite shock',lambda:[reject(lambda:a.simulate(dict(region=m.regions[0],industry='B',amount=x))) for a,x in [(m,0),(m,float('nan'))]])
for key,value in [('basis','total'),('coverage','')]:
    bad=copy.deepcopy(p);bad['meta'][key]=value;check('reject metadata '+key,lambda:reject(lambda:r.RegionalModel(bad)))
bad=copy.deepcopy(p);bad['nodes'][0]['imports']=None;check('reject partially missing optional data',lambda:reject(lambda:r.RegionalModel(bad)))
bad=copy.deepcopy(p);bad['Z'][0][0]=-1;check('reject negative intermediate transactions',lambda:reject(lambda:r.RegionalModel(bad)))
bad=copy.deepcopy(q);bad['Z']=[[100,0],[0,100]];check('reject singular technology',lambda:reject(lambda:r.RegionalModel(bad)))
bad=copy.deepcopy(q);bad['nodes'][0]['output']=0;check('reject nonzero transactions at zero output',lambda:reject(lambda:r.RegionalModel(bad)))
zero=copy.deepcopy(q);zero['nodes'][0]['output']=0;zero['Z']=[[0,0],[0,40]];zm=r.RegionalModel(zero)
check('zero output LQ undefined',lambda:close(zm.info()['rows'][0]['lq'] is None,True))
check('zero output shock rejected',lambda:reject(lambda:zm.simulate(dict(region='R0',industry='A',amount=1))))
w=workbook(p);loaded=r.read_workbook(raw(w),'test.xlsx');check('XLSX round trip',lambda:close(loaded.L,m.L))
# Reverse both transaction axes and final-demand row order, preserving identity.
w=workbook(p);ws=w['transactions'];values=list(ws.values);w.remove(ws);ws=w.create_sheet('transactions');ws.append(['code']+list(reversed(values[0][1:])))
for row in reversed(values[1:]):ws.append([row[0]]+list(reversed(row[1:])))
ws=w['final_demand'];values=list(ws.values);w.remove(ws);ws=w.create_sheet('final_demand');ws.append(values[0])
for row in reversed(values[1:]):ws.append(row)
check('workbook code-based reordering',lambda:close(r.read_workbook(raw(w),'reordered.xlsx').L,m.L))
w=workbook(p);w['transactions']['B1']='unknown';check('reject incorrect workbook codes',lambda:reject(lambda:r.read_workbook(raw(w),'bad.xlsx')))
r.dispatch('regional_demo',{});old=r.regional_model
check('failed import keeps prior regional state',lambda:reject(lambda:r.initialize(raw(w),'bad.xlsx')))
assert r.regional_model is old
w=workbook(p);w['nodes'].delete_rows(1,w['nodes'].max_row);check('empty sheet readable error',lambda:reject(lambda:r.read_workbook(raw(w),'empty.xlsx')))
model=SimpleNamespace(metrics=True,meta={**p['meta'],'modelBasis':'domestic'},codes=m.codes,Zd=m.Z,x=m.x,va=m.va,Zm=np.diag(m.imports))
csv='code,region,industry,name\n'+'\n'.join(','.join(str(o[k]) for k in ['code','region','industry','name']) for o in p['nodes'])
mapped=r.from_current(model,dict(csv=csv,confirmed=True,coverage='selected'))
check('current model mapping preserves domestic matrix',lambda:close(mapped.L,m.L))
check('current mapping requires explicit region-table confirmation',lambda:reject(lambda:r.from_current(model,dict(csv=csv,confirmed=False))))
if '--template' in sys.argv:
    w=workbook(p);ws=w.create_sheet('guide',0);ws.append(['항목','입력 안내'])
    for row in [
        ['자료 구분','전체 숫자는 학습용 가상 자료입니다. 실제 지역 통계가 아닙니다. 본인 자료로 모든 관련 시트를 교체하세요.'],
        ['metadata','year 연도, unit 금액 단위, price 가격 기준, source 출처. coverage: 전국 전체 national / 일부 지역 selected. basis는 domestic. 실제 자료는 data_type을 observed로 변경.'],
        ['nodes','각 행은 지역×산업. code는 고유, region 지역명, industry 공통 산업 코드, name 공통 명칭, output 총산출. 모든 지역에 동일 산업 목록 필요.'],
        ['선택 열','value_added 부가가치, imports 해외 수입 중간투입(열합), employment 기준 취업자수(명). 없는 자료는 해당 열 전체를 비우세요. 일부 빈 셀은 거부합니다.'],
        ['transactions','국산 중간거래금액. 행은 공급 지역×산업, 열은 구매 지역×산업. 행·열 code는 nodes와 같아야 합니다. 수입을 포함하지 마세요.'],
        ['final_demand','국산 최종수요. 행 code, 열은 각 최종수요 목적지 지역과 exports(해외 수출). 없는 경우 시트 전체 삭제. 음수 재고는 유지합니다.'],
        ['단위와 범위','모든 금액은 같은 단위·연도·가격·분류를 사용합니다. 누락 지역을 0으로 간주하지 않습니다. 일반 전국표로 지역간 거래를 추정하지 않습니다.'],
        ['빈 셀·수식','실제 0은 숫자 0. 수식 대신 계산된 숫자 값을 붙여 넣으세요. 산업별 합계 행은 넣지 마세요.'],
        ['검사','2~30개 지역, 최대 600개 지역×산업 조합, 30MB 이하 XLSX. 수급 균형 잔차는 앱에서 확인하세요.'],
        ['해석','지역 시나리오 선택은 생산물의 생산지입니다. 지출자 거주지가 아닙니다. 취업 결과는 영구 신규 일자리가 아닙니다.']]:ws.append(row)
    for sheet in w:
        sheet.freeze_panes='B2';sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:cell.font=Font(color='FFFFFF',bold=True);cell.fill=PatternFill('solid',fgColor='1D6B50')
        for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=22
    w['guide'].column_dimensions['B'].width=100
    for row in w['guide'].iter_rows(min_row=2):row[1].alignment=Alignment(wrap_text=True,vertical='top');w['guide'].row_dimensions[row[0].row].height=48
    w['metadata'].column_dimensions['B'].width=65
    w.save('regional-template.xlsx')
Path('regional-verification.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,demoProduction100=s['production'],maxInverseResidual=m.inverse_error),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=len(checks),demoProduction100=s['production']),ensure_ascii=False))
