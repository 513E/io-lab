"""Two-polar, five-factor SDA following the course's Syrquin equations."""
import numpy as np

FACTORS=['국내최종수요','수출','최종재 수입대체','중간재 수입대체','기술구조']

def snapshot(model):
    if model.meta['modelBasis']!='domestic' or model.x is None or model.Zm is None:
        raise ValueError('국산·수입 거래금액표와 총산출이 모두 필요합니다. 계수표만으로 시점 비교를 할 수 없습니다.')
    roles=['fd_'+g for g in ['consumption','investment','inventory','exports']]+['fm_'+g for g in ['consumption','investment','inventory']]
    missing=[r for r in roles if r not in model.extra]
    if missing:raise ValueError('소비·고정투자·재고·국산 수출 및 수입 최종수요를 연결하세요. 자료 연결에서 부족한 항목: '+', '.join(missing))
    domestic=sum(model.extra['fd_'+g] for g in ['consumption','investment','inventory'])
    imports=sum(model.extra['fm_'+g] for g in ['consumption','investment','inventory'])
    return dict(codes=model.codes,names=model.names,meta=dict(model.meta),x=model.x.tolist(),zd=model.Zd.tolist(),zm=model.Zm.tolist(),f=(domestic+imports).tolist(),mf=imports.tolist(),e=model.extra['fd_exports'].tolist(),sources=dict(model.extra_sources))

def demo():
    out=[]
    for t in range(2):
        a=np.array([[.18,.08,.06],[.12,.22,.1],[.07,.09,.14]])+t*np.array([[.01,-.01,.0],[.0,.015,.01],[.005,.0,-.01]])
        s=np.array([[.2,.3,.25],[.15,.2,.3],[.1,.15,.2]])-t*.03
        m=np.array([.22,.15,.08])-t*np.array([.02,.01,.01])
        f=np.array([110.,150.,180.])+t*np.array([12.,-8.,20.]);e=np.array([30.,50.,20.])+t*np.array([8.,12.,-4.])
        ad=a*(1-s);x=np.linalg.solve(np.eye(3)-ad,(1-m)*f+e)
        out.append(dict(codes=['A','B','C'],names=['농림수산업','제조업','서비스업'],meta=dict(year=str(2015+5*t),price='생산자가격',unit='가상 금액단위',level='학습용 3부문',source='학습용 가상자료 · 실제 통계 아님'),x=x.tolist(),zd=(ad*x).tolist(),zm=(a*s*x).tolist(),f=f.tolist(),mf=(m*f).tolist(),e=e.tolist(),demo=True))
    return out

def compare(p):
    snaps=p['periods']
    if len(snaps)!=2 or not all(snaps):raise ValueError('기준시점과 비교시점을 모두 저장하세요.')
    a,b=snaps;n=len(a['codes'])
    if not n or n>600 or len(set(a['codes']))!=n or set(a['codes'])!=set(b['codes']) or len(b['codes'])!=n:raise ValueError('두 시점의 산업 코드와 분류가 정확히 같아야 합니다.')
    order=[b['codes'].index(c) for c in a['codes']]
    if a['names']!=[b['names'][i] for i in order]:raise ValueError('산업 명칭이 달라 분류 개편 여부를 확인해야 합니다. 동일 분류로 재집계한 자료를 사용하세요.')
    for key,label in [('unit','금액 단위'),('price','가격 평가기준'),('level','산업분류')]:
        if not a['meta'].get(key) or a['meta'].get(key)!=b['meta'].get(key):raise ValueError('두 자료의 '+label+'이 같아야 합니다.')
    try:y0,y1=int(a['meta']['year']),int(b['meta']['year'])
    except (ValueError,KeyError,TypeError):raise ValueError('자료 설정에서 두 시점의 연도를 지정하세요.')
    if y1<=y0:raise ValueError('비교시점 연도는 기준시점보다 뒤여야 합니다.')
    if bool(a.get('demo'))!=bool(b.get('demo')):raise ValueError('가상 예제와 실제 자료를 섞어 비교할 수 없습니다.')
    basis=p.get('basis')
    if basis not in ['nominal','real']:raise ValueError('가격 기준을 선택하세요.')
    if not p.get('confirmed'):raise ValueError('분류와 가격 기준의 일치 여부를 확인한 뒤 확인란을 선택하세요.')
    if basis=='real' and not str(p.get('baseYear','')).isdigit():raise ValueError('공통 불변가격 기준연도를 입력하세요. 앱이 자동으로 물가를 조정하지 않습니다.')
    vals=[]
    for k,s in enumerate(snaps):
        d={}
        for key in ['x','zd','zm','f','mf','e']:
            v=np.asarray(s[key],dtype=float);shape=(n,n) if key in ['zd','zm'] else (n,)
            if v.shape!=shape or not np.isfinite(v).all():raise ValueError('자료의 크기 또는 수치에 문제가 있습니다: '+key)
            if k:v=v[np.ix_(order,order)] if v.ndim==2 else v[order]
            d[key]=v
        x=d['x']
        if np.any(x<0):raise ValueError('총산출은 음수일 수 없습니다.')
        if np.any((x==0)&(np.any(np.abs(d['zd'])>1e-9,axis=0)|np.any(np.abs(d['zm'])>1e-9,axis=0))):raise ValueError('총산출 0인 산업의 투입계수를 정의할 수 없습니다.')
        d['A']=(d['zd']+d['zm'])/np.where(x==0,1,x);d['Am']=d['zm']/np.where(x==0,1,x)
        if np.any((abs(d['A'])<1e-14)&(abs(d['Am'])>1e-12)) or np.any((abs(d['f'])<1e-14)&(abs(d['mf'])>1e-12)):raise ValueError('합계가 0인데 수입액이 존재하여 수입 비율을 정의할 수 없습니다.')
        d['S']=np.divide(d['Am'],d['A'],out=np.zeros((n,n)),where=abs(d['A'])>=1e-14)
        d['M']=np.divide(d['mf'],d['f'],out=np.zeros(n),where=abs(d['f'])>=1e-14)
        mat=np.eye(n)-(d['A']-d['Am'])
        if np.linalg.cond(mat)>1e10:raise ValueError('투입구조가 불안정하여 분해할 수 없습니다.')
        d['L']=np.linalg.inv(mat);d['balance']=x-(d['zd'].sum(1)+d['f']-d['mf']+d['e'])
        vals.append(d)
    u,v=vals
    zeros=0
    for ratio,key in [('S','A'),('M','f')]:
        z0=abs(u[key])<1e-14;z1=abs(v[key])<1e-14;zeros+=int(np.sum(z0|z1))
        u[ratio][z0]=v[ratio][z0];v[ratio][z1]=u[ratio][z1]
    df=v['f']-u['f'];de=v['e']-u['e'];dm=v['M']-u['M'];ds=v['S']-u['S'];da=v['A']-u['A']
    # Exact complementary paths: current L/structure with initial volumes vs vice versa.
    pa=np.column_stack([v['L']@((1-v['M'])*df),v['L']@de,-v['L']@(dm*u['f']),-v['L']@((ds*u['A'])@u['x']),v['L']@(((1-v['S'])*da)@u['x'])])
    la=np.column_stack([u['L']@((1-u['M'])*df),u['L']@de,-u['L']@(dm*v['f']),-u['L']@((ds*v['A'])@v['x']),u['L']@(((1-u['S'])*da)@v['x'])])
    change=v['x']-u['x'];methods={}
    for name,parts in [('paasche',pa),('laspeyres',la),('average',(pa+la)/2)]:
        residual=change-parts.sum(1)
        methods[name]=dict(parts=parts.tolist(),totals=parts.sum(0).tolist(),residual=residual.tolist(),residualTotal=float(residual.sum()),explained=float(parts.sum()))
    return dict(codes=a['codes'],names=a['names'],meta=[s['meta'] for s in snaps],x0=u['x'].tolist(),x1=v['x'].tolist(),change=change.tolist(),totalChange=float(change.sum()),methods=methods,factors=FACTORS,basis=basis,baseYear=p.get('baseYear',''),demo=bool(a.get('demo')),zeroConventions=zeros,balanceMax=[float(np.max(abs(d['balance']))) for d in vals],balanceRelative=[float(np.max(abs(d['balance'])/np.maximum(abs(d['x']),1))) for d in vals])
