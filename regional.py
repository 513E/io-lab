"""Interregional IO: explicit region-industry identities and domestic transactions."""
import csv, io, json
import numpy as np
import openpyxl


def txt(v):return '' if v is None else str(v).strip()
def num(v):
    try:x=float(str(v).replace(',',''))
    except (TypeError,ValueError):raise ValueError('빈 셀 또는 비수치가 있습니다. 없는 항목은 열 전체를 비우고, 실제 0은 0으로 입력하세요.')
    if not np.isfinite(x):raise ValueError('유한한 숫자만 입력하세요.')
    return x
def optional(rows,key):
    values=[r.get(key) for r in rows]
    if all(txt(v)=='' for v in values):return None
    if any(txt(v)=='' for v in values):raise ValueError(key+' 열이 일부만 채워져 있습니다. 전체 산업의 값이 필요합니다.')
    return [num(v) for v in values]
def percent(a,b):return float(a/b*100) if b!=0 else None

class RegionalModel:
    def __init__(self,p):
        self.meta=dict(p.get('meta',{}));self.nodes=[dict(o) for o in p['nodes']];n=len(self.nodes);self.n=n
        if not 2<=n<=600:raise ValueError('지역×산업 조합은 2~600개를 지원합니다.')
        for k in ['year','unit','price','source','coverage']:
            self.meta[k]=txt(self.meta.get(k))
            if not self.meta[k]:raise ValueError('metadata에 '+k+'를 입력하세요.')
        if self.meta.get('basis')!='domestic':raise ValueError('국산 거래만 연결하세요. 해외 수입은 imports 열에 별도로 입력합니다.')
        if self.meta['coverage'] not in ['national','selected']:raise ValueError('coverage는 national 또는 selected입니다.')
        for o in self.nodes:
            for k in ['code','region','industry','name']:
                o[k]=txt(o.get(k))
                if not o[k]:raise ValueError('code, region, industry, name을 모두 입력하세요.')
        self.codes=[o['code'] for o in self.nodes]
        if len(set(self.codes))!=n:raise ValueError('지역×산업 code가 중복됩니다. 각 조합의 고유 코드를 사용하세요.')
        self.regions=list(dict.fromkeys(o['region'] for o in self.nodes));self.industries=list(dict.fromkeys(o['industry'] for o in self.nodes))
        if not 2<=len(self.regions)<=30:raise ValueError('서로 다른 2~30개 지역이 필요합니다. 전국표에 지역 이름을 임의로 붙이지 마세요.')
        pairs=[(o['region'],o['industry']) for o in self.nodes]
        if len(set(pairs))!=n or n!=len(self.regions)*len(self.industries):raise ValueError('각 지역에 같은 산업분류가 한 번씩 있어야 합니다. 부재 산업은 확인된 0으로 명시하세요.')
        self.names={}
        for o in self.nodes:
            if o['industry'] in self.names and self.names[o['industry']]!=o['name']:raise ValueError('같은 산업 코드의 명칭이 지역마다 다릅니다.')
            self.names[o['industry']]=o['name']
        self.x=np.array([num(o['output']) for o in self.nodes]);self.Z=np.asarray(p['Z'],dtype=float)
        if self.Z.shape!=(n,n) or not np.isfinite(self.Z).all() or np.any(self.Z<0) or np.any(self.x<0):raise ValueError('국산 중간거래는 N×N 비음수 금액, 총산출은 비음수여야 합니다.')
        zero=self.x==0
        if np.any(abs(self.Z[:,zero])>1e-9) or np.any(abs(self.Z[zero,:])>1e-9):raise ValueError('총산출 0인 지역·산업에 중간거래가 있습니다.')
        self.va=optional(self.nodes,'value_added');self.imports=optional(self.nodes,'imports');self.jobs=optional(self.nodes,'employment')
        for key in ['va','imports','jobs']:
            v=getattr(self,key)
            if v is not None:
                v=np.array(v);setattr(self,key,v)
                if key!='va' and np.any(v<0):raise ValueError('수입 중간투입과 취업자수는 음수일 수 없습니다.')
                if np.any(abs(v[zero])>1e-9):raise ValueError('총산출 0인 조합에 부가가치·수입·취업자가 있습니다.')
        den=np.where(zero,1,self.x);self.A=self.Z/den
        mat=np.eye(n)-self.A
        try:
            if np.linalg.cond(mat)>1e10:raise ValueError('불안정한 투입구조입니다. 총산출·단위를 확인하세요.')
            self.L=np.linalg.inv(mat)
        except np.linalg.LinAlgError:raise ValueError('생산유발계수 역행렬을 구할 수 없습니다.')
        self.inverse_error=float(np.max(abs(mat@self.L-np.eye(n))))
        if self.inverse_error>1e-8 or np.min(self.L)<-1e-8:raise ValueError('생산 가능한 국산 투입구조가 아닙니다. 거래표와 총산출을 확인하세요.')
        self.v=None if self.va is None else self.va/den;self.m=None if self.imports is None else self.imports/den;self.e=None if self.jobs is None else self.jobs/den
        self.F=None;self.exports=None
        if p.get('F') is not None:
            self.F=np.asarray(p['F'],dtype=float);self.exports=np.asarray(p['exports'],dtype=float)
            if self.F.shape!=(n,len(self.regions)) or self.exports.shape!=(n,) or not np.isfinite(self.F).all() or not np.isfinite(self.exports).all():raise ValueError('final_demand의 지역 열과 exports를 모두 입력하세요.')
            if np.any(abs(self.F[zero,:])>1e-9) or np.any(abs(self.exports[zero])>1e-9):raise ValueError('총산출 0인 조합에 최종수요가 있습니다.')
        self.indices={r:np.array([i for i,o in enumerate(self.nodes) if o['region']==r]) for r in self.regions}
        self.demo=bool(p.get('demo',False));self.input_error=None;self.output_error=None
        if self.va is not None and self.imports is not None:self.input_error=float(np.max(abs(self.x-self.Z.sum(0)-self.va-self.imports)))
        if self.F is not None:self.output_error=float(np.max(abs(self.x-self.Z.sum(1)-self.F.sum(1)-self.exports)))
    def info(self):
        totals={r:float(self.x[ix].sum()) for r,ix in self.indices.items()};industry={k:sum(self.x[i] for i,o in enumerate(self.nodes) if o['industry']==k) for k in self.industries};whole=float(self.x.sum())
        rows=[]
        for i,o in enumerate(self.nodes):
            regional=totals[o['region']];national=industry[o['industry']]
            rows.append(dict(code=o['code'],region=o['region'],industry=o['industry'],name=o['name'],output=float(self.x[i]),valueAdded=None if self.va is None else float(self.va[i]),withinShare=percent(self.x[i],regional),industryRegionShare=percent(self.x[i],national),lq=float((self.x[i]/regional)/(national/whole)) if regional>0 and national>0 and whole>0 else None))
        groups=[];trade=np.zeros((len(self.regions),len(self.regions)));final=np.zeros_like(trade) if self.F is not None else None
        for ri,r in enumerate(self.regions):
            ix=self.indices[r];inside=float(self.Z[np.ix_(ix,ix)].sum());domInput=float(self.Z[:,ix].sum());domSales=float(self.Z[ix,:].sum());x=totals[r]
            groups.append(dict(region=r,output=x,valueAdded=None if self.va is None else float(self.va[ix].sum()),employment=None if self.jobs is None else float(self.jobs[ix].sum()),withinInput=inside,otherInput=domInput-inside,imports=None if self.imports is None else float(self.imports[ix].sum()),withinSales=inside,otherSales=domSales-inside,outputShare=percent(x,whole)))
            for ci,c in enumerate(self.regions):trade[ri,ci]=self.Z[np.ix_(ix,self.indices[c])].sum()
            if final is not None:final[ri,:]=self.F[ix,:].sum(0)
        # VA location (rows) by domestic final-demand destination (columns).
        vaFlows=None
        if self.F is not None and self.v is not None:
            by=self.v[:,None]*(self.L@self.F)
            vaFlows=np.vstack([by[ix,:].sum(0) for ix in self.indices.values()]).tolist()
        return dict(meta=self.meta,demo=self.demo,n=self.n,regions=self.regions,industries=[dict(code=k,name=self.names[k]) for k in self.industries],rows=rows,groups=groups,trade=trade.tolist(),finalTrade=None if final is None else final.tolist(),vaFlows=vaFlows,inverseError=self.inverse_error,inputError=self.input_error,outputError=self.output_error,hasVA=self.va is not None,hasImports=self.imports is not None,hasEmployment=self.jobs is not None,zeroOutput=int(np.sum(self.x==0)))
    def simulate(self,p):
        region=p.get('region');industry=p.get('industry');amount=num(p.get('amount'));weight=p.get('weight','output')
        if region not in self.indices or (industry!='all' and industry not in self.industries):raise ValueError('지역과 산업을 선택하세요.')
        if amount==0:raise ValueError('0이 아닌 수요 변화액을 입력하세요.')
        if weight not in ['output','equal']:raise ValueError('산업별 배분 방식을 확인하세요.')
        ix=self.indices[region];chosen=np.array([i for i in ix if industry=='all' or self.nodes[i]['industry']==industry]);active=chosen[self.x[chosen]>0]
        if not len(active):raise ValueError('선택 조합의 기준 산출이 0입니다. 기존 투입구조로 신규 생산을 추정할 수 없습니다.')
        if industry!='all' and len(active)!=1:raise ValueError('선택한 지역·산업을 확인하세요.')
        weights=self.x[active]/self.x[active].sum() if weight=='output' else np.ones(len(active))/len(active)
        f=np.zeros(self.n);f[active]=amount*weights;dx=self.L@f
        if not np.isfinite(dx).all():raise ValueError('수요 변화액이 너무 큽니다.')
        if np.any(self.x+dx < -1e-7):raise ValueError('감소폭이 기준 총산출을 초과합니다.')
        dv=None if self.v is None else self.v*dx;dm=None if self.m is None else self.m*dx;de=None if self.e is None else self.e*dx
        own=float(dx[ix].sum());total=float(dx.sum());isolated=float(np.linalg.solve(np.eye(len(ix))-self.A[np.ix_(ix,ix)],f[ix]).sum());regional=[];rows=[]
        for r,indices in self.indices.items():regional.append(dict(region=r,production=float(dx[indices].sum()),direct=float(f[indices].sum()),valueAdded=None if dv is None else float(dv[indices].sum()),imports=None if dm is None else float(dm[indices].sum()),employment=None if de is None else float(de[indices].sum())))
        for i,o in enumerate(self.nodes):rows.append(dict(code=o['code'],region=o['region'],industry=o['industry'],name=o['name'],production=float(dx[i]),direct=float(f[i]),valueAdded=None if dv is None else float(dv[i]),imports=None if dm is None else float(dm[i]),employment=None if de is None else float(de[i])))
        return dict(region=region,industry=industry,amount=amount,weight=weight,production=total,own=own,other=total-own,isolated=isolated,feedback=own-isolated,multiplier=total/amount,valueAdded=None if dv is None else float(dv.sum()),imports=None if dm is None else float(dm.sum()),employment=None if de is None else float(de.sum()),regions=regional,rows=rows,allocation=[dict(code=self.codes[i],amount=float(f[i])) for i in active],excludedZeroOutput=int(len(chosen)-len(active)))


def demo_data():
    regions=['가상 북부','가상 중부','가상 남부'];industries=[('A','농림수산업'),('B','제조업'),('C','서비스업')];n=9
    base=np.array([[.14,.055,.025],[.1,.23,.075],[.045,.09,.16]])
    a=np.zeros((n,n))
    for r in range(3):
        for s in range(3):a[r*3:(r+1)*3,s*3:(s+1)*3]=base*(.82 if r==s else (.17 if (r+1)%3==s else .11))
    f=np.array([[40,6,5],[52,14,10],[120,15,12],[9,55,8],[18,95,20],[20,19,70],[12,9,80],[15,23,60],[13,16,95]],dtype=float);exports=np.array([6,30,9,8,45,7,12,32,8],dtype=float)
    x=np.linalg.solve(np.eye(n)-a,f.sum(1)+exports);z=a*x;imports=np.tile([.06,.14,.045],3)*x;va=x-z.sum(0)-imports;employment=x*np.tile([2.,.7,1.5],3)
    nodes=[dict(code=str(r+1)+'-'+k,region=regions[r],industry=k,name=name,output=float(x[r*3+j]),value_added=float(va[r*3+j]),imports=float(imports[r*3+j]),employment=float(employment[r*3+j])) for r in range(3) for j,(k,name) in enumerate(industries)]
    return dict(meta=dict(year='2020',unit='백만원',price='가상 기준가격',source='학습용 가상 3지역×3산업 · 실제 지역 통계 아님',coverage='selected',basis='domestic'),demo=True,nodes=nodes,Z=z.tolist(),F=f.tolist(),exports=exports.tolist())

def read_workbook(raw,filename):
    book=openpyxl.load_workbook(io.BytesIO(bytes(raw)),read_only=True,data_only=True)
    try:
        if not {'metadata','nodes','transactions'}.issubset(book.sheetnames):raise ValueError('지역 양식의 metadata, nodes, transactions 시트가 필요합니다. 일반 표는 상단 자료 설정 후 지역 연결 CSV를 사용하세요.')
        def rows(name):
            if book[name].max_row>605 or book[name].max_column>602:raise ValueError(name+' 시트의 크기가 지원 범위를 초과합니다.')
            result=[list(r) for r in book[name].iter_rows(values_only=True) if any(v is not None for v in r)]
            if not result:raise ValueError(name+' 시트가 비어 있습니다.')
            return result
        mr=rows('metadata');meta={txt(r[0]):txt(r[1]) for r in mr[1:] if len(r)>1};nr=rows('nodes');headers=[txt(c) for c in nr[0]]
        if len(set(headers))!=len(headers) or not {'code','region','industry','name','output'}.issubset(headers):raise ValueError('nodes의 필수 열과 중복 헤더를 확인하세요.')
        nodes=[dict(zip(headers,r)) for r in nr[1:]];codes=[txt(o['code']) for o in nodes]
        if len(codes)>600:raise ValueError('지역×산업 조합은 최대 600개입니다.')
        tr=rows('transactions');col=[txt(c) for c in tr[0][1:]];row=[txt(r[0]) for r in tr[1:]]
        if len(col)!=len(codes) or len(row)!=len(codes) or len(set(col))!=len(col) or len(set(row))!=len(row) or set(col)!=set(codes) or set(row)!=set(codes):raise ValueError('transactions의 행·열 code가 nodes와 정확히 일치해야 합니다.')
        by={txt(r[0]):r[1:] for r in tr[1:]};Z=[[num(by[c][col.index(k)]) for k in codes] for c in codes]
        data=dict(meta=meta,nodes=nodes,Z=Z,demo=meta.get('data_type')=='synthetic')
        if 'final_demand' in book.sheetnames:
            fr=rows('final_demand');regions=list(dict.fromkeys(txt(o['region']) for o in nodes));cols=[txt(c) for c in fr[0][1:]];ids=[txt(r[0]) for r in fr[1:]]
            if len(ids)!=len(codes) or set(ids)!=set(codes) or len(cols)!=len(regions)+1 or len(set(cols))!=len(cols) or set(cols)!=set(regions+['exports']):raise ValueError('final_demand는 모든 code 행과 지역별 목적지 열, exports 열이 필요합니다.')
            by={txt(r[0]):r[1:] for r in fr[1:]};data['F']=[[num(by[c][cols.index(k)]) for k in regions] for c in codes];data['exports']=[num(by[c][cols.index('exports')]) for c in codes]
        data['meta']['source']=data['meta'].get('source') or filename
        return RegionalModel(data)
    finally:book.close()

def from_current(model,p):
    if model is None or not model.metrics:raise ValueError('상단에서 지역간 거래표를 먼저 불러오세요.')
    if not p.get('confirmed'):raise ValueError('현재 표가 지역간 국산 거래표임을 확인하세요.')
    if model.meta['modelBasis']!='domestic' or model.Zd is None or model.x is None:raise ValueError('국산 거래금액과 총산출이 필요합니다.')
    rows=list(csv.DictReader(io.StringIO(p['csv'].lstrip('\ufeff'))));ids=[txt(o.get('code')) for o in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(model.codes):raise ValueError('CSV의 code가 현재 표의 모든 산업 코드와 정확히 일치해야 합니다.')
    by={txt(o['code']):o for o in rows};nodes=[]
    for i,c in enumerate(model.codes):
        o=by[c];nodes.append(dict(code=c,region=o.get('region'),industry=o.get('industry'),name=o.get('name'),output=float(model.x[i]),value_added=None if model.va is None else float(model.va[i]),imports=None if model.Zm is None else float(model.Zm[:,i].sum())))
    return RegionalModel(dict(meta={**model.meta,'basis':'domestic','coverage':p.get('coverage','selected')},nodes=nodes,Z=model.Zd.tolist()))

regional_model=None

def initialize(raw,filename):
    global regional_model
    candidate=read_workbook(raw,filename);regional_model=candidate
    return candidate.info()
def dispatch(method,p,model=None):
    global regional_model
    if method=='regional_demo':regional_model=RegionalModel(demo_data());return regional_model.info()
    if method=='regional_map':
        candidate=from_current(model,p);regional_model=candidate;return candidate.info()
    if method=='regional_clear':regional_model=None;return dict(cleared=True)
    if regional_model is None:raise ValueError('지역 자료를 먼저 연결하세요.')
    if method=='regional_scenario':return regional_model.simulate(p)
    raise ValueError('지원하지 않는 지역 분석 요청입니다.')
