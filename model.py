"""Browser-local input-output analysis. Amounts retain the uploaded source unit."""
import io, json, math, re, csv
import numpy as np
import openpyxl
from advanced import AdvancedMixin

def clean(v):
    return str(v).replace('\n', ' ').strip() if v is not None else ''
def code(v):
    return str(int(v)) if isinstance(v, (float, int)) and float(v).is_integer() else clean(v)
def emit(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)
def value(rows,r,c):
    return rows[r][c] if 0<=r<len(rows) and 0<=c<len(rows[r]) else None
def cell(s):
    m=re.fullmatch(r'([A-Za-z]+)([1-9][0-9]*)',clean(s))
    if not m: raise ValueError('셀 주소는 C7처럼 입력하세요.')
    col=0
    for ch in m[1].upper(): col=col*26+ord(ch)-64
    return int(m[2])-1,col-1
def address(r,c):
    out=''
    c+=1
    while c: c,k=divmod(c-1,26);out=chr(k+65)+out
    return out+str(r+1)
def numeric(v):
    if isinstance(v,str): v=v.replace(',','').strip()
    if v is None or v=='' or isinstance(v,bool): raise ValueError('빈 셀 또는 비수치')
    x=float(v)
    if not math.isfinite(x): raise ValueError('유한하지 않은 수')
    return x

def auto_layout(rows):
    # The BOK format uses matching industry identifiers in a header and row axis.
    for h,row in enumerate(rows[:20]):
        if len(row)<3: continue
        cols=[(i,code(v)) for i,v in enumerate(row) if i>=2 and v is not None and not(code(v).isdigit() and int(code(v))>=9000)]
        if len(cols)<2: continue
        codes=[v for _,v in cols]
        if len(set(codes))!=len(codes): continue
        ri={code(r[0]):j for j,r in enumerate(rows[h+1:],h+1) if len(r)>1 and r[0] is not None}
        if all(c in ri for c in codes) and all(ri[c]==ri[codes[0]]+k for k,c in enumerate(codes)):
            return dict(header=h,start=ri[codes[0]],col=cols[0][0],codes=codes,ri=ri,ci={code(v):i for i,v in enumerate(row) if v is not None})
    return None

class IOModel(AdvancedMixin):
    def __init__(self,raw=None,filename='',book=None,mapping=None):
        self.filename=filename or '사용자 자료'
        if book is not None: self.book=book
        elif filename.lower().endswith('.csv'):
            s=bytes(raw).decode('utf-8-sig')
            self.book={'CSV':list(csv.reader(io.StringIO(s)))}
        else:
            wb=openpyxl.load_workbook(io.BytesIO(bytes(raw)),read_only=True,data_only=True)
            self.book={s.title:[list(r) for r in s.values] for s in wb.worksheets};wb.close()
        if not self.book: raise ValueError('비어 있는 파일입니다.')
        self.layouts={s:auto_layout(rows) for s,rows in self.book.items()}
        self.n=0;self.metrics=[];self.checks={};self.warnings=[];self.finals={};self.Z=None
        self.meta=dict(year='',price='기준가격 미지정',unit='원자료 단위',source=self.filename,basis='total',level='사용자 자료',kind='transactions')
        self.mapping=self.suggest()
        if mapping is not None: self.configure(mapping)
        elif self.mapping.get('auto'):
            try:self.configure(self.mapping)
            except (ValueError,KeyError,IndexError,np.linalg.LinAlgError) as e:self.n=0;self.metrics=[];self.warnings=['자동 분석을 완료하지 못했습니다. 자료 설정에서 범위를 확인하세요. '+str(e)]
        else:self.warnings=['시트는 열었습니다. 분석할 거래표 또는 투입계수표의 범위를 지정해 주세요.']

    def suggest(self):
        names=list(self.book)
        total=next((s for s in names if '총거래표' in s),'')
        domestic=next((s for s in names if '국산거래표' in s),'')
        imports=next((s for s in names if '수입거래표' in s),'')
        main=total or domestic or names[0];layout=self.layouts[main]
        text=' '.join(clean(v) for row in self.book[main][:10] for v in row[:3])
        year=re.search(r'(?:19|20)\d{2}년?',text)
        unit=next((u for u in ['십억원','백만원','천원','억원','조원','원'] if re.search(r'(?:단위[^\w]*|,\s*)'+u,text)), '원자료 단위')
        if unit=='원자료 단위' and '백만원' in text:unit='백만원'
        d=dict(sheet=main,start='C7',n=3,codeStart='A7',nameStart='B7',output='',outputAxis='row',va='',vaAxis='row',domesticSheet='',domesticStart='C7',importsSheet='',importsStart='C7',year=year[0].replace('년','') if year else '',unit=unit,source=self.filename,price='생산자가격' if '생산자' in text+main else '기준가격 미지정',basis='total' if total else 'domestic' if domestic else 'total',kind='transactions',level='사용자 자료',auto=False)
        if layout and (total or domestic):
            d.update(start=address(layout['start'],layout['col']),n=len(layout['codes']),codeStart=address(layout['start'],0),nameStart=address(layout['start'],1),level='산업 '+str(len(layout['codes']))+'부문',auto=True)
            for field,k in [('output','9790'),('va','9690')]:
                if k in layout['ri']:d[field]=address(layout['ri'][k],layout['col'])
            for field,s in [('domestic',domestic),('imports',imports)]:
                if s and s!=main and self.layouts[s]:d[field+'Sheet']=s;d[field+'Start']=address(self.layouts[s]['start'],self.layouts[s]['col'])
            if not d['output']:d['auto']=False
        # Portable one-sheet template, with arbitrary year, currency, and sector count.
        for s,rows in self.book.items():
            if rows and [clean(x).lower() for x in rows[0][:2]]==['code','name']:
                n=next((i-2 for i,x in enumerate(rows[0]) if clean(x).lower()=='output'),0)
                if n>0:
                    d.update(sheet=s,start='C2',n=n,codeStart='A2',nameStart='B2',output=address(1,n+2),outputAxis='col',va=address(1,n+3) if clean(value(rows,0,n+3)).lower()=='value_added' else '',vaAxis='col',auto=False)
                    break
        return d

    def configure(self,p):
        n=int(p.get('n',0))
        if not 1<=n<=600:raise ValueError('산업 수는 1~600개로 지정하세요.')
        self.n=n
        self.meta={k:clean(p.get(k,'')) for k in ['year','price','unit','source','basis','kind','level']}
        self.meta['unit']=self.meta['unit'] or '원자료 단위';self.meta['source']=self.meta['source'] or self.filename
        self.meta['level']=self.meta['level'] or '사용자 분류'
        if self.meta['basis'] not in ['total','domestic'] or self.meta['kind'] not in ['transactions','coefficients']:raise ValueError('자료 유형을 선택하세요.')
        rows=self.book[p['sheet']];r,c=cell(p['start'])
        def column(start,default):
            if not start:return default
            a,b=cell(start);return [code(value(rows,a+i,b)) for i in range(n)]
        self.codes=column(p.get('codeStart'),[str(i+1) for i in range(n)])
        self.names=column(p.get('nameStart'),self.codes)
        if len(set(self.codes))!=n or any(not v for v in self.codes+self.names):raise ValueError('산업 코드/이름 범위에 빈 값이나 중복 코드가 있습니다.')
        def matrix(sheet,start):
            a,b=cell(start);rr=self.book[sheet]
            try:return np.array([[numeric(value(rr,a+i,b+j)) for j in range(n)] for i in range(n)])
            except (ValueError,TypeError):raise ValueError(sheet+': '+start+'부터 '+str(n)+'×'+str(n)+' 범위에 빈 셀 또는 비수치가 있습니다. 표 범위와 수식의 저장된 값을 확인하세요.')
        def vector(key):
            if not p.get(key):return None
            a,b=cell(p[key]);vertical=p.get(key+'Axis')=='col'
            try:return np.array([numeric(value(rows,a+i if vertical else a,b if vertical else b+i)) for i in range(n)])
            except (ValueError,TypeError):raise ValueError(key+': 합계/계수 벡터에 빈 셀 또는 비수치가 있습니다.')
        Z=matrix(p['sheet'],p['start']);dom=matrix(p['domesticSheet'],p['domesticStart']) if p.get('domesticSheet') else None
        imp=matrix(p['importsSheet'],p['importsStart']) if p.get('importsSheet') else None
        # Automatic imports align every table by the exact industry codes.
        if p.get('auto'):
            for sheet in [p.get('domesticSheet'),p.get('importsSheet')]:
                if sheet and self.layouts[sheet]['codes']!=self.codes:raise ValueError('연결한 시트의 산업 순서가 다릅니다. 자료 설정에서 범위를 확인하세요.')
        self.x=vector('output'); vv=vector('va');is_coeff=self.meta['kind']=='coefficients'
        if not is_coeff and self.x is None:raise ValueError('거래금액표에는 산업별 총산출 벡터가 필요합니다.')
        if self.x is not None and np.any(self.x<0):raise ValueError('총산출이 음수입니다. 합계 행·열 또는 산업 범위를 확인하세요.')
        zero=(self.x==0) if self.x is not None else np.zeros(n,dtype=bool)
        if not is_coeff and np.any(zero) and (np.any(np.abs(Z[:,zero])>1e-9) or (vv is not None and np.any(np.abs(vv[zero])>1e-9))):raise ValueError('총산출 0인 산업에 투입 또는 부가가치가 있습니다. 범위와 단위를 확인하세요.')
        denominator=np.where(zero,1,self.x) if self.x is not None else None
        if self.meta['basis']=='domestic':dom=Z
        elif dom is None and imp is not None:dom=Z-imp
        elif dom is not None and imp is None:imp=Z-dom
        if self.meta['basis']=='total' and dom is not None and imp is not None:
            residual=float(np.max(np.abs(Z-dom-imp)));self.checks['총거래 − 국산 − 수입 (원자료 단위)']=residual
            if residual>max(1e-6,float(np.max(np.abs(Z)))*1e-4):raise ValueError('총거래 = 국산 + 수입 관계가 맞지 않습니다. 시트 범위와 산업 순서를 확인하세요.')
        B=dom if dom is not None else Z
        self.meta['modelBasis']='domestic' if dom is not None else 'total'
        self.A=B if is_coeff else B/denominator[None,:]
        self.Am=imp if is_coeff else (imp/denominator[None,:] if imp is not None else None)
        self.Z=(Z*self.x[None,:] if is_coeff and self.x is not None else None) if is_coeff else Z
        self.Zd=(B*self.x[None,:] if is_coeff and self.x is not None else None) if is_coeff else B
        self.Zm=(imp*self.x[None,:] if is_coeff and imp is not None and self.x is not None else None) if is_coeff else imp
        self.va=vv*self.x if is_coeff and vv is not None and self.x is not None else (None if is_coeff else vv)
        self.v=vv if is_coeff else (vv/denominator if vv is not None else None)
        try:self.L=np.linalg.inv(np.eye(n)-self.A)
        except np.linalg.LinAlgError:raise ValueError('역행렬을 구할 수 없습니다. 투입계수와 총산출 범위를 확인하세요.')
        residual=float(np.max(np.abs((np.eye(n)-self.A)@self.L-np.eye(n))))
        if not np.isfinite(self.L).all() or residual>=1e-8 or np.linalg.cond(np.eye(n)-self.A)>1e10:raise ValueError('안정적으로 역행렬을 구할 수 없습니다. 거래금액/계수 구분과 총산출을 확인하세요.')
        if np.min(self.A)>=-1e-10 and np.min(self.L)<-1e-7:raise ValueError('생산가능한 투입계수 구조가 아닙니다. 총산출과 단위를 확인하세요.')
        self.checks['(I − A) × L − I 최대 절대 잔차']=residual
        self.M=self.Am@self.L if self.Am is not None else None
        self.V=self.v[:,None]*self.L if self.v is not None else None
        if self.M is not None:self.checks['Am × L − M 최대 절대 잔차']=float(np.max(np.abs(self.Am@self.L-self.M)))
        if self.V is not None:self.checks['diag(v) × L − V 최대 절대 잔차']=float(np.max(np.abs(self.v[:,None]*self.L-self.V)))
        cols=self.L.sum(0);rs=self.L.sum(1);self.metrics=[]
        for i,(co,na) in enumerate(zip(self.codes,self.names)):
            self.metrics.append(dict(code=co,name=na,output=float(self.x[i]) if self.x is not None else None,valueAdded=float(self.va[i]) if self.va is not None else None,valueRate=float(self.v[i]*100) if self.v is not None else None,importRate=float(self.Am[:,i].sum()*100) if self.Am is not None else None,multiplier=float(cols[i]),vaMultiplier=float(self.V[:,i].sum()) if self.V is not None else None,importMultiplier=float(self.M[:,i].sum()) if self.M is not None else None,backward=float(cols[i]/cols.mean()) if cols.mean()!=0 else None,forward=float(rs[i]/rs.mean()) if rs.mean()!=0 else None))
        self.finals={}
        fs=p.get('domesticSheet') or (p['sheet'] if self.meta['modelBasis']=='domestic' else '')
        layout=self.layouts.get(fs)
        if fs and layout and not is_coeff:
            for co,na in [('9140','수출'),('9111','민간소비지출'),('9112','정부소비지출'),('9121','민간고정자본형성'),('9122','정부고정자본형성'),('9190','최종수요계')]:
                if co in layout['ci'] and all(k in layout['ri'] for k in self.codes):
                    try:self.finals[co]=dict(name=na,values=np.array([numeric(value(self.book[fs],layout['ri'][k],layout['ci'][co])) for k in self.codes]))
                    except (ValueError,TypeError):pass
        if p.get('final') and not is_coeff:
            self.finals['custom']=dict(name=clean(p.get('finalName')) or '지정한 최종수요',values=vector('final'))
        self.warnings=[]
        if np.any(zero):self.warnings.append('총산출 0인 산업은 '+str(int(zero.sum()))+'개입니다. 거래금액도 0인 투입 열의 계수는 0으로 처리합니다.')
        if self.meta['modelBasis']=='total':self.warnings.append('총거래 기반 모형입니다. 수입이 분리되지 않아 결과를 국내 생산유발액으로 해석할 수 없습니다.')
        if self.M is None:self.warnings.append('수입 자료가 없어 수입유발액을 계산하지 않습니다.')
        if self.V is None:self.warnings.append('부가가치 자료가 없어 부가가치유발액을 계산하지 않습니다.')
        self.mapping=dict(p)
        # Record a readable layout for manually mapped source tables.
        if not self.layouts[p['sheet']]:self.layouts[p['sheet']]=dict(header=max(0,r-1),start=r,col=c,codes=self.codes,manual=True)

        self.advanced_init()

    def info(self):
        ready=bool(self.metrics)
        return dict(advanced=self.advanced_info() if ready else {},n=self.n if ready else 0,level=self.meta['level'],sectors=self.metrics,sheets=list(self.book),checks=self.checks,warnings=self.warnings,meta=self.meta,filename=self.filename,mapping=self.mapping,ready=ready,capabilities=dict(profile=ready and self.Z is not None,simulate=ready,imports=ready and self.M is not None,va=ready and self.V is not None),finals=[dict(code=k,name=v['name']) for k,v in self.finals.items()],output=float(self.x.sum()) if ready and self.x is not None else None,valueAdded=float(self.va.sum()) if ready and self.va is not None else None,importRate=float(self.Zm.sum()/self.x.sum()*100) if ready and self.Zm is not None and self.x is not None and self.x.sum()>0 else None)

    def explore(self,p):
        sheet=p.get('sheet',list(self.book)[0]);rows=self.book[sheet];axis=p.get('axis','row');layout=self.layouts[sheet]
        if layout and not layout.get('manual'):
            h=layout['header'];start=layout['start'];col=layout['col']
            ro=[dict(code=code(row[0]),name=clean(value(rows,i,1)),index=i) for i,row in enumerate(rows) if i>=start and row and row[0] is not None]
            co=[dict(code=code(v),name=clean(value(rows,h+1,j)),index=j) for j,v in enumerate(rows[h]) if j>=col and v is not None]
            text=' '.join(clean(v) for row in rows[:h] for v in row[:3]);u='배' if '계수' in sheet or '배' in text else ('백만원' if '백만원' in text else self.meta['unit'])
        else:
            ro=[dict(code=str(i+1),name=' · '.join(clean(v) for v in row[:3])[:100] or '빈 행',index=i) for i,row in enumerate(rows)]
            co=[dict(code=address(0,j)[:-1],name=clean(value(rows,0,j)) or '열',index=j) for j in range(max((len(r) for r in rows),default=0))]
            u='원자료값'
        opts=ro if axis=='row' else co
        if not opts:return dict(choices=[],selected=dict(code='',name=''),cells=[],axis=axis)
        chosen=next((o for o in opts if o['code']==p.get('code')),opts[0]);other=co if axis=='row' else ro;cells=[]
        for o in other:
            v=value(rows,chosen['index'],o['index']) if axis=='row' else value(rows,o['index'],chosen['index'])
            if v is not None and not isinstance(v,(str,int,float,bool)):v=clean(v)
            label=chosen['name']+' '+o['name'];uu='%' if '%' in label or '구성비' in label else ('배' if '계수' in label else u)
            cells.append(dict(code=o['code'],name=o['name'],value=v,unit=uu,money=(uu==self.meta['unit'] and uu not in ['원자료값','배','%'])))
        return dict(choices=opts,selected=chosen,cells=cells,axis=axis)

    def profile(self,code):
        if self.Z is None:raise ValueError('거래금액 자료가 없어 연결 금액을 표시할 수 없습니다.')
        j=self.codes.index(code)
        def ranked(a):return sorted([dict(code=c,name=n,total=float(a[i])) for i,(c,n) in enumerate(zip(self.codes,self.names))],key=lambda r:r['total'],reverse=True)
        return dict(metrics=self.metrics[j],upstream=ranked(self.Z[:,j]),downstream=ranked(self.Zd[j,:]))

    def simulate(self,p):
        if not self.metrics:raise ValueError('자료 설정을 먼저 완료하세요.')
        f=np.zeros(self.n);items=[]
        for item in p:
            j=self.codes.index(str(item['code']));v=numeric(item['amount']);baseline=None
            if item.get('mode')=='percent':
                if v < -100:raise ValueError('감소율은 -100% 이상이어야 합니다.')
                if item.get('base') not in self.finals:raise ValueError('선택한 최종수요 자료가 없습니다.')
                baseline=float(self.finals[item['base']]['values'][j])
                if baseline<=0:raise ValueError('기준수요가 0 이하입니다. 금액 입력을 사용하세요.')
                amount=baseline*v/100
            else:amount=v*numeric(item.get('factor',1))
            f[j]+=amount;items.append(dict(code=self.codes[j],name=self.names[j],amount=amount,baseline=baseline))
        if not np.any(f):raise ValueError('합산한 수요 변화액이 모두 0입니다.')
        x=self.L@f;m=self.M@f if self.M is not None else None;v=self.V@f if self.V is not None else None
        if not np.isfinite(x).all():raise ValueError('입력 금액이 너무 큽니다.')
        if self.x is not None and np.any(self.x+x < -1e-6):raise ValueError('감소폭이 기준자료의 생산액을 초과합니다.')
        out=[dict(code=c,name=n,production=float(x[i]),direct=float(f[i]),indirect=float(x[i]-f[i]),imports=float(m[i]) if m is not None else None,valueAdded=float(v[i]) if v is not None else None) for i,(c,n) in enumerate(zip(self.codes,self.names))]
        out.sort(key=lambda r:abs(r['production']),reverse=True)
        return dict(demand=float(f.sum()),production=float(x.sum()),imports=float(m.sum()) if m is not None else None,valueAdded=float(v.sum()) if v is not None else None,direct=float(f.sum()),indirect=float((x-f).sum()),multiplier=float(x.sum()/f.sum()) if np.all(f>=0) and f.sum()>0 else None,rows=out,items=items)

model=None
def initialize(raw,filename=''):
    global model
    model=IOModel(raw,filename)
    return emit(model.info())
def dispatch(method,payload):
    global model
    if model is None:raise ValueError('자료를 먼저 불러오세요.')
    data=json.loads(payload)
    if method=='configure':
        candidate=IOModel(filename=model.filename,book=model.book,mapping=data);model=candidate
        return emit(model.info())
    if method=='preview':
        rows=model.book[data['sheet']]
        return emit(dict(rows=[[clean(v) for v in r[:18]] for r in rows[:18]],height=len(rows),width=max((len(r) for r in rows),default=0)))
    if method in ['price','ghosh','employment','decompose','bind_extra','attach_employment','attach_reference']:
        if not model.metrics:raise ValueError('분석 자료를 먼저 연결하세요.')
        return emit(getattr(model,method)(data))
    if method=='validation_report':return emit(model.validation_report())
    if method=='explore':return emit(model.explore(data))
    if method=='profile':return emit(model.profile(data))
    if method=='simulate':return emit(model.simulate(data))
    raise ValueError('알 수 없는 분석 요청입니다.')
