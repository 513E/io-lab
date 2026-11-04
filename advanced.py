"""Extended input-output methods. No data is silently borrowed across datasets."""
import csv, io, re
import numpy as np

GROUPS=[('consumption','소비',['9111','9112']),('investment','고정투자',['9121','9122']),('inventory','재고·귀중품',['9131','9132']),('exports','수출',['9140'])]
ROLES={'wage':'피용자보수','operating':'영업잉여','tax':'순생산세','exports':'수출액','importsTotal':'수입계','supplyTotal':'총공급계','jobs':'취업계수','employees':'고용계수','jobsMultiplier':'공표 취업유발계수','employeesMultiplier':'공표 고용유발계수','providedL':'제공된 생산유발계수','providedM':'제공된 수입유발계수','providedV':'제공된 부가가치유발계수',**{'fd_'+k:'국산 최종수요 · '+n for k,n,_ in GROUPS},**{'fm_'+k:'수입 최종수요 · '+n for k,n,_ in GROUPS}}
def text(v):return '' if v is None else str(v).strip()
def key(v):return str(int(v)) if isinstance(v,(int,float)) and float(v).is_integer() else text(v)
def get(rows,r,c):return rows[r][c] if 0<=r<len(rows) and 0<=c<len(rows[r]) else None
def number(v):
    if v is None or text(v)=='':raise ValueError('빈 값은 수치로 연결할 수 없습니다.')
    n=float(text(v).replace(',',''))
    if not np.isfinite(n):raise ValueError('유한한 수를 입력하세요.')
    return n
def coord(s):
    m=re.fullmatch(r'([A-Za-z]+)([1-9][0-9]*)',text(s))
    if not m:raise ValueError('C7 같은 셀 주소를 입력하세요.')
    c=0
    for ch in m[1].upper():c=c*26+ord(ch)-64
    return int(m[2])-1,c-1
def ratio(a,b):return float(a/b*100) if a is not None and b is not None and b!=0 else None
def total(v):return float(v.sum()) if v is not None else None

class AdvancedMixin:
    def _header(self,sheet):
        if not sheet or sheet not in self.book:return None
        rows=self.book[sheet]
        layout=self.layouts.get(sheet)
        if layout and 'ri' in layout:return layout
        for h,row in enumerate(rows[:20]):
            ci={key(v):i for i,v in enumerate(row) if v is not None}
            ri={key(r[0]):i for i,r in enumerate(rows[h+1:],h+1) if r and r[0] is not None}
            if all(c in ri for c in self.codes) and ('9140' in ci or all(c in ci for c in self.codes)):
                return dict(header=h,ri=ri,ci=ci)
        return None
    def _column(self,sheet,code):
        h=self._header(sheet)
        if not h or code not in h['ci']:return None
        try:return np.array([number(get(self.book[sheet],h['ri'][c],h['ci'][code])) for c in self.codes])
        except (KeyError,ValueError,TypeError):return None
    def _row(self,sheet,code):
        h=self._header(sheet)
        if not h or code not in h['ri']:return None
        try:return np.array([number(get(self.book[sheet],h['ri'][code],h['ci'][c])) for c in self.codes])
        except (KeyError,ValueError,TypeError):return None
    def _square(self,sheet):
        h=self._header(sheet)
        if not h:return None
        try:return np.array([[number(get(self.book[sheet],h['ri'][c],h['ci'][k])) for k in self.codes] for c in self.codes])
        except (KeyError,ValueError,TypeError):return None
    def _put(self,role,data,source):
        if data is not None:self.extra[role]=data;self.extra_sources[role]=source
    def advanced_init(self):
        self.extra={};self.extra_sources={};self.reference=None;self.provided_effects={}
        main=self.mapping['sheet'];coeff=self.meta['kind']=='coefficients'
        for role,code in [('wage','9610'),('operating','9621'),('tax','9630')]:
            a=self._row(main,code)
            if a is not None:
                if not coeff:a=np.divide(a,self.x,out=np.zeros(self.n),where=self.x!=0)
                self._put(role,a,main+' · '+code+'행 / 총산출' if not coeff else main+' · '+code+'행')
        if not coeff:
            for role,code in [('exports','9140'),('importsTotal','9329'),('supplyTotal','9390')]:self._put(role,self._column(main,code),main+' · '+code+'열')
        for role,s in [('providedL','생산유발계수'),('providedM','수입유발계수'),('providedV','부가가치유발계수')]:
            if s in self.book:self._put(role,self._square(s),s+' · 산업코드 정렬')
        ds=self.mapping.get('domesticSheet') or (main if self.meta['basis']=='domestic' else '')
        ms=self.mapping.get('importsSheet')
        if not coeff:
            for prefix,sheet in [('fd_',ds),('fm_',ms)]:
                for group,_,codes in GROUPS:
                    parts=[self._column(sheet,c) for c in codes]
                    if all(a is not None for a in parts):self._put(prefix+group,sum(parts),str(sheet)+' · '+'+'.join(codes))
        for metric,name in [('production','생산'),('imports','수입'),('valueAdded','부가가치')]:
            sheet=next((s for s in self.book if '최종수요 항목별' in s and name+'유발액' in s),'')
            if not sheet:continue
            parts={}
            for group,_,codes in GROUPS:
                arrays=[self._column(sheet,c) for c in codes]
                if all(a is not None for a in arrays):parts[group]=sum(arrays)
            if len(parts)==4:self.provided_effects[metric]=dict(source=sheet,parts=parts)
        self._refresh_structure()
    def _refresh_structure(self):
        self.structure=[]
        full=(self.meta['basis']=='total')
        Ztotal=self.Z if full else (self.Zd+self.Zm if self.Zd is not None and self.Zm is not None else None)
        self.Ztotal=Ztotal
        for j,m in enumerate(self.metrics):
            x=self.x[j] if self.x is not None else None
            inter=Ztotal[:,j].sum() if Ztotal is not None else None
            dom=self.Zd[:,j].sum() if self.meta['modelBasis']=='domestic' and self.Zd is not None else None
            export=self.extra.get('exports');imports=self.extra.get('importsTotal');supply=self.extra.get('supplyTotal')
            if supply is None and imports is not None and self.x is not None:supply=self.x+imports
            self.structure.append(dict(code=m['code'],name=m['name'],exportRate=ratio(export[j],x) if export is not None else None,importRate=ratio(imports[j],supply[j]) if imports is not None and supply is not None else None,valueAddedRate=m['valueRate'],intermediateRate=ratio(inter,x),localization=ratio(dom,inter),selfInput=ratio(Ztotal[j,j],inter) if Ztotal is not None else None,selfCoefficient=ratio(Ztotal[j,j],x) if Ztotal is not None else None,backward=m['backward'],forward=m['forward']))
    def advanced_info(self):
        if not hasattr(self,'extra'):return {}
        domestic=self.meta['modelBasis']=='domestic'
        return dict(roles=[dict(code=k,name=n) for k,n in ROLES.items()],sources=self.extra_sources,structure=self.structure,
                    price=domestic and any(k in self.extra for k in ['wage','tax','operating']),
                    ghosh=domestic and self.x is not None and self.Zd is not None,
                    employment=any(k in self.extra for k in ['jobs','employees','jobsMultiplier','employeesMultiplier']),
                    employmentUnit=getattr(self,'employment_unit','명/10억원'),
                    decomposition=list(set(self.provided_effects)|({'production'} if any('fd_'+k in self.extra for k,_,_ in GROUPS) else set())),reference=bool(self.reference))
    def bind_extra(self,p):
        role=p['role']
        if role not in ROLES:raise ValueError('지원하지 않는 자료 항목입니다.')
        rows=self.book[p['sheet']];r,c=coord(p['start']);matrix=role.startswith('provided')
        try:
            if matrix:a=np.array([[number(get(rows,r+i,c+j)) for j in range(self.n)] for i in range(self.n)])
            else:a=np.array([number(get(rows,r+i if p['axis']=='col' else r,c if p['axis']=='col' else c+i)) for i in range(self.n)])
        except (TypeError,ValueError):raise ValueError('지정한 범위에 빈 값 또는 비수치가 있습니다. 산업 순서·범위를 확인하세요.')
        if role in ['wage','tax','operating'] and p.get('kind')!='coefficient':
            if self.x is None:raise ValueError('비용 금액을 계수로 바꾸려면 총산출이 필요합니다.')
            if np.any((self.x==0)&(a!=0)):raise ValueError('총산출 0인 산업에 비용이 있습니다.')
            a=np.divide(a,self.x,out=np.zeros(self.n),where=self.x!=0)
        if role in ['jobs','employees','jobsMultiplier','employeesMultiplier']:
            if np.any(a<0):raise ValueError('노동계수는 음수가 될 수 없습니다.')
            u=p.get('employmentUnit','명/10억원')
            labor=['jobs','employees','jobsMultiplier','employeesMultiplier']
            if any(k in self.extra and k!=role for k in labor) and u!=getattr(self,'employment_unit','명/10억원'):raise ValueError('연결된 노동계수의 단위와 다릅니다. 모든 계수를 같은 단위의 CSV로 다시 연결하세요.')
            if u=='명/10억원' and self.meta['unit'] not in ['원','천원','백만원','억원','십억원','조원']:raise ValueError('외화 자료에는 명/원자료 1단위 계수를 연결하세요.')
            self.employment_unit=u
        self._put(role,a,p['sheet']+'!'+p['start']+' · '+('정방행렬' if matrix else p['axis']))
        self._refresh_structure();return self.advanced_info()
    def attach_employment(self,p):
        # Explicit CSV attachment: one row per exact industry code. No 33-to-380 copying.
        rows=list(csv.DictReader(io.StringIO(p['csv'].lstrip('\ufeff'))))
        if not rows or 'code' not in rows[0]:raise ValueError('CSV 첫 행에 code와 jobs/ employees/ jobsMultiplier/ employeesMultiplier 열이 필요합니다.')
        ids=[text(r['code']) for r in rows]
        if len(ids)!=len(set(ids)) or set(ids)!=set(self.codes):raise ValueError('CSV 산업 코드가 현재 자료와 정확히 일치해야 합니다. 누락·중복·다른 분류를 확인하세요.')
        by={text(r['code']):r for r in rows};new={}
        for k in ['jobs','employees','jobsMultiplier','employeesMultiplier']:
            if k in rows[0] and any(text(r.get(k)) for r in rows):
                a=np.array([number(by[c][k]) for c in self.codes])
                if np.any(a<0):raise ValueError('노동계수는 음수가 될 수 없습니다.')
                new[k]=a
        if not new:raise ValueError('노동계수 열을 찾지 못했습니다.')
        u=p.get('unit','명/10억원')
        if u=='명/10억원' and self.meta['unit'] not in ['원','천원','백만원','억원','십억원','조원']:raise ValueError('외화 자료에는 명/원자료 1단위 계수를 연결하세요.')
        for k in ['jobs','employees','jobsMultiplier','employeesMultiplier']:
            self.extra.pop(k,None);self.extra_sources.pop(k,None)
        for k,a in new.items():self._put(k,a,p.get('source','사용자 노동계수 CSV'))
        self.employment_unit=u;return self.advanced_info()
    def attach_reference(self,p):
        snap=p['snapshot']
        if self.meta['year']!='2023' or self.codes!=[s['code'] for s in snap['sectors']] or self.x is None or not np.allclose(self.x,[s['output'] for s in snap['sectors']],rtol=1e-10,atol=.01):raise ValueError('예시 보조자료와 현재 산업표가 일치하지 않습니다.')
        self.reference=p.get('benchmarks')
        if p.get('employment'):
            e=p['employment'];by={r['code']:r for r in e['rows']}
            for role,keyname in [('jobs','employment'),('employees','employee'),('jobsMultiplier','officialEmploymentMultiplier'),('employeesMultiplier','officialEmployeeMultiplier')]:self._put(role,np.array([by[c][keyname] for c in self.codes]),e['source'])
            self.employment_unit='명/10억원'
        return self.advanced_info()
    def decompose(self,p):
        metric=p.get('metric','production');sector=p.get('code','all');origin=p.get('origin','provided')
        j=None if sector=='all' else self.codes.index(sector)
        if origin=='provided' and metric in self.provided_effects:
            parts=self.provided_effects[metric]['parts'];source=self.provided_effects[metric]['source'];scope='수입 최종재 포함' if metric=='imports' else '제공된 유발액 시트'
        else:
            multiplier={'production':self.L,'imports':self.M,'valueAdded':self.V}.get(metric)
            if multiplier is None:raise ValueError('해당 유발계수를 계산할 자료가 없습니다.')
            parts={k:multiplier@self.extra['fd_'+k] for k,_,_ in GROUPS if 'fd_'+k in self.extra}
            if not parts:raise ValueError('최종수요 항목 자료를 연결하세요.')
            includes=metric=='imports' and all('fm_'+k in self.extra for k in parts)
            if includes:parts={k:a+self.extra['fm_'+k] for k,a in parts.items()}
            scope='수입 최종재 포함' if includes else ('수입 중간재만 · 최종재 자료 없음' if metric=='imports' else '연결한 국산 최종수요로 재계산')
            source='현재 모형 재계산'
        amounts={k:float(a.sum() if j is None else a[j]) for k,a in parts.items()};net=sum(amounts.values())
        out=[dict(code=k,name=n,amount=amounts[k],share=amounts[k]/net*100 if net!=0 else None) for k,n,_ in GROUPS if k in amounts]
        return dict(rows=out,total=net,source=source,scope=scope,complete=len(parts)==4,metric=metric,sector=sector)
    def price(self,p):
        if self.meta['modelBasis']!='domestic':raise ValueError('수입가격 고정 모형에는 국산 투입계수를 연결하세요.')
        shock=np.zeros(self.n);applied=[]
        for role in ['wage','tax','operating']:
            rate=number(p.get(role,0))/100
            if rate < -1:raise ValueError('비용 감소율은 -100% 이상이어야 합니다.')
            if rate==0:continue
            if role not in self.extra:raise ValueError(ROLES[role]+' 자료를 먼저 연결하세요.')
            part=self.extra[role]*rate
            if p.get('code','all')!='all':
                j=self.codes.index(p['code']);mask=np.zeros(self.n);mask[j]=1;part=part*mask
            shock+=part;applied.append(dict(role=role,rate=rate*100))
        if not applied:raise ValueError('0이 아닌 비용 변화율을 입력하세요.')
        dp=self.L.T@shock
        if np.any(1+dp<0):raise ValueError('모형 가격이 음수가 됩니다. 충격 크기를 줄이세요.')
        rows=[dict(code=c,name=n,direct=float(shock[i]*100),indirect=float((dp[i]-shock[i])*100),change=float(dp[i]*100)) for i,(c,n) in enumerate(zip(self.codes,self.names))]
        rows.sort(key=lambda r:abs(r['change']),reverse=True)
        return dict(rows=rows,weighted=float(np.dot(self.x,dp)/self.x.sum()*100) if self.x is not None and self.x.sum()>0 else None,max=float(dp.max()*100),min=float(dp.min()*100),inputs=applied,scope=p.get('code','all'))
    def ghosh(self,p):
        if self.meta['modelBasis']!='domestic' or self.x is None or self.Zd is None:raise ValueError('국산거래표와 총산출을 먼저 연결하세요.')
        if np.any((self.x==0)&(np.abs(self.Zd).sum(1)>1e-9)):raise ValueError('총산출 0인 산업에 국산 판매가 있어 배분계수를 구할 수 없습니다.')
        B=np.divide(self.Zd,self.x[:,None],out=np.zeros_like(self.Zd),where=self.x[:,None]!=0)
        G=np.linalg.inv(np.eye(self.n)-B);q=self.x-self.Zd.sum(0)
        j=self.codes.index(p['code']);v=number(p['amount']);delta=np.zeros(self.n)
        if p.get('mode')=='percent':
            if v < -100 or q[j]<=0:raise ValueError('기초투입이 양수이고 감소율이 -100% 이상이어야 합니다.')
            delta[j]=q[j]*v/100
        else:delta[j]=v*number(p.get('factor',1))
        if delta[j]==0:raise ValueError('0이 아닌 기초투입 변화량을 입력하세요.')
        if q[j]+delta[j]<-1e-6:raise ValueError('기초투입 감소가 기준액을 초과합니다.')
        dx=G.T@delta
        if np.any(self.x+dx < -1e-6):raise ValueError('감소 후 산출가치가 음수가 됩니다.')
        rows=[dict(code=c,name=n,change=float(dx[i]),direct=float(delta[i]),indirect=float(dx[i]-delta[i])) for i,(c,n) in enumerate(zip(self.codes,self.names))];rows.sort(key=lambda r:abs(r['change']),reverse=True)
        residual=float(np.max(np.abs((np.eye(self.n)-B)@G-np.eye(self.n))))
        return dict(rows=rows,total=float(dx.sum()),direct=float(delta.sum()),baseline=float(q[j]),residual=residual,inputs=dict(code=p['code'],mode=p.get('mode'),amount=v,factor=p.get('factor',1)))
    def employment(self,p):
        result=self.simulate(p['items']);by={r['code']:r for r in result['rows']};x=np.array([by[c]['production'] for c in self.codes]);f=np.array([by[c]['direct'] for c in self.codes])
        u=getattr(self,'employment_unit','명/10억원')
        multipliers={'원':1e-9,'천원':1e-6,'백만원':.001,'억원':.1,'십억원':1,'조원':1000}
        scale=1 if u=='명/원자료 1단위' else multipliers.get(self.meta['unit'])
        if scale is None:raise ValueError('금액 단위와 노동계수의 기준 단위를 맞추세요.')
        computed={};official={}
        for k in ['jobs','employees']:
            if k in self.extra:computed[k]=dict(total=float(np.dot(self.extra[k],x)*scale),direct=float(np.dot(self.extra[k],f)*scale))
            if k+'Multiplier' in self.extra:official[k]=float(np.dot(self.extra[k+'Multiplier'],f)*scale)
        if not computed and not official:raise ValueError('현재 산업 분류의 노동계수를 연결하세요. 예시 보조자료는 대분류만 제공됩니다.')
        rows=[dict(code=c,name=n,jobs=float(self.extra['jobs'][i]*x[i]*scale) if 'jobs' in self.extra else None,employees=float(self.extra['employees'][i]*x[i]*scale) if 'employees' in self.extra else None) for i,(c,n) in enumerate(zip(self.codes,self.names))]
        rows.sort(key=lambda r:abs(r['jobs'] if r['jobs'] is not None else r['employees'] or 0),reverse=True)
        return dict(computed=computed,official=official,rows=rows,coefficientUnit=u,demand=result['demand'],inputs=result['items'],sources={k:v for k,v in self.extra_sources.items() if k in ['jobs','employees','jobsMultiplier','employeesMultiplier']})
    def validation_report(self):
        rows=[]
        def compare(name,calc,ref,source,tol=1e-8,unit='배'):
            if calc is None or ref is None:return
            a=np.asarray(calc);b=np.asarray(ref);diff=np.abs(a-b);flat=int(np.argmax(diff));idx=np.unravel_index(flat,diff.shape) if diff.ndim else ()
            rows.append(dict(name=name,calculated=float(a[idx]) if idx else float(a),reference=float(b[idx]) if idx else float(b),difference=float(diff.max()),tolerance=tol,pass_=bool(diff.max()<=tol),source=source,unit=unit,location=' / '.join(self.codes[i] for i in idx) if idx and all(i<self.n for i in idx) else '전체',relative=float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))))
        compare('역행렬 항등식',(np.eye(self.n)-self.A)@self.L,np.eye(self.n),'현재 모형 · 수치 잔차')
        for name,role,a in [('생산유발계수 L','providedL',self.L),('수입유발계수 M','providedM',self.M),('부가가치유발계수 V','providedV',self.V)]:compare(name,a,self.extra.get(role),self.extra_sources.get(role,''))
        for metric,mat in [('production',self.L),('imports',self.M),('valueAdded',self.V)]:
            if mat is None or metric not in self.provided_effects:continue
            for group,label,_ in GROUPS:
                if 'fd_'+group not in self.extra:continue
                a=mat@self.extra['fd_'+group]
                if metric=='imports':
                    if 'fm_'+group not in self.extra:continue
                    a=a+self.extra['fm_'+group]
                ref=self.provided_effects[metric]['parts'][group]
                compare({'production':'생산','imports':'수입','valueAdded':'부가가치'}[metric]+' · '+label,a,ref,self.provided_effects[metric]['source'],max(1e-6,float(np.max(np.abs(ref)))*1e-9),self.meta['unit'])
        benchmark=[]
        if self.reference:
            x=total(self.x);z=total(self.Ztotal);d=total(self.Zd);m=total(self.Zm);v=total(self.va)
            calc={'output':x/1e6,'valueAdded':v/1e6,'intermediateRate':ratio(z,x),'localization':ratio(d,z),'importDependence':ratio(m,x),'valueAddedRate':ratio(v,x),'exportRate':ratio(total(self.extra.get('exports')),x),'importRate':ratio(total(self.extra.get('importsTotal')),total(self.extra.get('supplyTotal')))}
            parts=[self.extra.get('fd_'+k) for k,_,_ in GROUPS]
            if all(a is not None for a in parts):
                f=sum(parts);den=float(f.sum())
                for k,mat in [('weightedProduction',self.L),('weightedValueAdded',self.V),('weightedImports',self.M)]:calc[k]=float((mat@f).sum()/den) if mat is not None and den else None
            for spec in self.reference['rows']:
                if spec['key'] not in calc or calc[spec['key']] is None:continue
                value=calc[spec['key']];delta=abs(value-spec['expected']);benchmark.append(dict(name=spec['name'],calculated=value,reference=spec['expected'],difference=delta,tolerance=spec['tolerance'],pass_=delta<=spec['tolerance'],unit=spec['unit'],source=spec['sheet']+'!'+spec['cell'],location='전산업',relative=None))
        return dict(rows=rows,benchmarks=benchmark,provided=any(k.startswith('provided') for k in self.extra),note='행렬 비교는 동일 모형·산업코드로 정렬합니다. 금액표는 원자료 반올림을 고려한 허용오차를 사용합니다. 공표 노동유발계수는 집계 방식이 달라 이 통과/불일치 판정에 넣지 않습니다.')
