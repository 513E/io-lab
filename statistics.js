'use strict';
const statsDefs=[
 ['multiplier','생산유발계수','배','L의 열합'],['exportRate','수출률','%','수출액 / 총산출 ×100'],['importRate','수입률','%','수입계 / 총공급계 ×100'],['valueAddedRate','부가가치율','%','부가가치 / 총투입 ×100'],['intermediateRate','중간투입률','%','총중간투입 / 총투입 ×100'],['localization','국산화율','%','국산 중간투입 / 총중간투입 ×100'],['selfInput','자기부문 투입비','%','자기부문 중간투입 / 총중간투입 ×100'],['backward','영향력계수','지수','L 열합 / 열합 평균'],['forward','감응도계수','지수','L 행합 / 행합 평균'],['output','총산출','원자료 단위','현재 자료의 총산출 금액']
];
const statsColors=['#287c64','#557eaf','#c08b3c','#986aa8','#b95d70','#657b84'];
let statsRows=[],statsAvailable=[],statsSelected='',statsTab='distribution',statsPCA=null,statsCluster=0,statsWorker=null,statsJob=0,statsRunning=false;
const statsDef=k=>{const d=statsDefs.find(d=>d[0]===k);return {key:k,name:k==='multiplier'?metricNames.multiplier:d?.[1]||k,unit:k==='output'?info?.meta.unit||'원자료 단위':d?.[2]||'',definition:d?.[3]||''};};
const statsFormat=(x,k)=>IOStats.finite(x)?num(x,k==='output'?2:4):'자료 없음';
function statsCaption(){return [info?.meta.year||'연도 미지정',info?.level,info?.n+'개 산업',modelLabel()].join(' · ');}
function statsSource(){return String(info?.meta.source||info?.filename||'출처 미지정');}
function resetStatistics(){$('stats-empty').textContent='위에서 분석할 자료를 불러오면 통계 탐색을 시작할 수 있습니다.';statsJob++;statsWorker?.terminate();statsWorker=null;statsRunning=false;statsRows=[];statsAvailable=[];statsPCA=null;statsSelected='';$('stats-workspace').hidden=true;$('stats-empty').hidden=false;$('stats-badge').textContent='자료 연결 대기';$('stats-search').value='';$('stats-sector').replaceChildren();$('stats-pca-result').hidden=true;for(const id of ['stats-summary','stats-distribution-chart','stats-correlation-chart','stats-heatmap','stats-pca-chart'])$(id).replaceChildren();}
let statsLibraryLoad=null,statsRefresh=0;
const statsLibraryReady=()=>typeof globalThis.IOStats==='object'&&['finite','describe','correlation','pcaCluster'].every(k=>typeof globalThis.IOStats[k]==='function');
function ensureStatsLibrary(){
 if(statsLibraryReady())return Promise.resolve();
 if(statsLibraryLoad)return statsLibraryLoad;
 statsLibraryLoad=new Promise((resolve,reject)=>{
  const script=document.createElement('script');
  const timer=setTimeout(()=>finish(Error('통계 계산 파일 응답이 지연됩니다.')),15000);
  let finished=false;
  function finish(error){if(finished)return;finished=true;clearTimeout(timer);script.onload=script.onerror=null;script.remove();error?reject(error):resolve();}
  script.src='./stats-math.js?v=20261117-stats2&retry=1';
  script.onload=()=>finish(statsLibraryReady()?null:Error('통계 계산 파일을 초기화하지 못했습니다.'));
  script.onerror=()=>finish(Error('통계 계산 파일을 내려받지 못했습니다.'));
  document.head.appendChild(script);
 }).finally(()=>{statsLibraryLoad=null;});
 return statsLibraryLoad;
}
async function refreshStatistics(){
 const version=loadVersion,refresh=++statsRefresh;
 if(!info?.ready){resetStatistics();return;}
 try{
  if(!statsLibraryReady()){
   $('stats-workspace').hidden=true;$('stats-empty').hidden=false;
   $('stats-empty').textContent='통계 계산 파일을 다시 준비하고 있습니다. 다른 분석 기능은 사용할 수 있습니다.';
   await ensureStatsLibrary();
  }
  if(version!==loadVersion||refresh!==statsRefresh||!info?.ready)return;
  populateStatistics();
 }catch(e){
  if(version!==loadVersion||refresh!==statsRefresh)return;
  resetStatistics();$('stats-badge').textContent='통계 연결 확인 필요';
  $('stats-empty').textContent='통계 기능을 준비하지 못했습니다. 불러온 자료와 다른 분석 기능은 유지됩니다. ';
  const retry=document.createElement('button');retry.type='button';retry.className='text-button';retry.textContent='통계 다시 연결';retry.onclick=refreshStatistics;$('stats-empty').appendChild(retry);
  console.warn('통계 초기화 실패:',e);
 }
}
function populateStatistics(){
 if(!info?.ready){resetStatistics();return;}
 const structure=new Map((info.advanced?.structure||[]).map(r=>[r.code,r]));
 statsRows=info.sectors.map(r=>{const s=structure.get(r.code)||{};return {code:r.code,name:r.name,output:r.output,multiplier:r.multiplier,backward:r.backward,forward:r.forward,valueAddedRate:r.valueRate,exportRate:s.exportRate??null,importRate:s.importRate??null,intermediateRate:s.intermediateRate??null,localization:s.localization??null,selfInput:s.selfInput??null};});
 statsAvailable=statsDefs.filter(([k])=>statsRows.some(r=>IOStats.finite(r[k]))).map(([k])=>k);
 $('stats-workspace').hidden=false;$('stats-empty').hidden=true;$('stats-badge').textContent=statsCaption();
 const opts=statsAvailable.map(k=>({code:k,name:statsDef(k).name}));
 for(const id of ['stats-metric','stats-x','stats-y']){const keep=$(id).value;$(id).innerHTML=opts.map(o=>'<option value="'+esc(o.code)+'">'+esc(o.name)+' ('+esc(statsDef(o.code).unit)+')</option>').join('');if(statsAvailable.includes(keep))$(id).value=keep;}
 if(!statsSelected){$('stats-x').value=statsAvailable.includes('exportRate')?'exportRate':statsAvailable[0];$('stats-y').value=statsAvailable.includes('importRate')?'importRate':statsAvailable[1]||statsAvailable[0];}
 const defaults=new Set(['multiplier','exportRate','importRate','valueAddedRate','localization','selfInput']);
 $('stats-features').innerHTML=statsDefs.map(([k])=>'<label title="'+esc(statsDef(k).definition)+'"><input type="checkbox" value="'+k+'" '+(statsAvailable.includes(k)?(defaults.has(k)?'checked':''):'disabled')+'> '+esc(statsDef(k).name)+(statsAvailable.includes(k)?'':' · 자료 없음')+'</label>').join('');
 $('stats-k').value=String(Math.max(2,Math.min(3,statsRows.length-1)));$('stats-profile').disabled=!info.capabilities.profile;
 updateStatsSelection();invalidatePCA();renderStatistics();
}
function updateStatsSelection(){const rows=statsRows.filter(r=>match(r,$('stats-search').value));const old=statsSelected;options($('stats-sector'),rows,old);statsSelected=$('stats-sector').value;}
function pickStats(code){statsSelected=code;$('stats-search').value='';options($('stats-sector'),statsRows,code);const point=statsPCA?.rows.find(r=>r.code===code);if(point)statsCluster=point.cluster;renderStatistics();}
function renderStatistics(){if(!statsRows.length)return;renderDistribution();renderCorrelation();if(statsPCA)renderPCA();}
function statsTable(headers,rows){return '<div class="table-scroll tall"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+esc(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
const svgText=(x,y,t,size=12,anchor='start',color='#52665c')=>'<text x="'+x+'" y="'+y+'" font-size="'+size+'" text-anchor="'+anchor+'" fill="'+color+'">'+esc(t)+'</text>';
function chartSVG(title,content){return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 510" role="img" aria-label="'+esc(title)+'" style="font-family:Arial, sans-serif;background:#fff"><title>'+esc(title)+'</title><rect width="760" height="510" fill="#fff"/>'+svgText(28,30,title,17,'start','#1c2938')+content+svgText(28,474,statsCaption(),10)+svgText(28,490,statsSource().slice(0,95),10)+'</svg>';}
function axisRange(values){let lo=Math.min(...values),hi=Math.max(...values);const gap=(hi-lo)*.08||Math.max(1,Math.abs(lo)*.1);return [lo-gap,hi+gap];}
function statsPoint(code,name,x,y,color,r=5,extra=''){const selected=code===statsSelected;return '<circle role="button" tabindex="0" data-stat-point="'+esc(code)+'" aria-label="'+esc(name+' '+extra)+'" cx="'+x+'" cy="'+y+'" r="'+(selected?r+2:r)+'" fill="'+color+'" fill-opacity="'+(selected?1:.72)+'" stroke="'+(selected?'#172d25':'#fff')+'" stroke-width="'+(selected?2:1)+'"><title>'+esc(name+' · '+extra)+'</title></circle>';}
function bindStatPoints(target){target.querySelectorAll('[data-stat-point]').forEach(p=>{p.onclick=()=>pickStats(p.dataset.statPoint);p.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pickStats(p.dataset.statPoint);}};});}
function renderDistribution(){
 const key=$('stats-metric').value,d=statsDef(key),valid=statsRows.filter(r=>IOStats.finite(r[key])),s=IOStats.describe(statsRows.map(r=>r[key]));
 if(!s.n)return;
 $('stats-summary').innerHTML=stat('산업 평균',num(s.mean,3),d.unit,'산업별 동일 가중치')+stat('중앙값',num(s.median,3),d.unit,'전체 분포의 가운데')+stat('표준편차',num(s.sd,3),d.unit,'분모 n · 현재 유효 산업')+stat('유효 산업',s.n,'개','결측 '+s.missing+'개 제외');
 let bins=$('stats-bins').value==='auto'?Math.max(3,Math.min(24,Math.ceil(Math.sqrt(s.n)))):Number($('stats-bins').value);if(s.min===s.max)bins=1;
 let [lo,hi]=s.min===s.max?axisRange([s.min]):[s.min,s.max];const counts=Array(bins).fill(0),width=(hi-lo)/bins;for(const r of valid)counts[Math.min(bins-1,Math.floor((r[key]-lo)/width))]++;
 const px=v=>64+(v-lo)/(hi-lo)*658,max=Math.max(...counts);let svg='';
 for(let i=0;i<=4;i++){const y=280-i/4*196;svg+='<path d="M64 '+y+'H722" stroke="#e8eeeb"/>'+svgText(54,y+4,num(max*i/4,1),10,'end');}
 for(let i=0;i<bins;i++){const h=counts[i]/max*196;svg+='<rect x="'+(64+i*658/bins+1)+'" y="'+(280-h)+'" width="'+Math.max(1,658/bins-2)+'" height="'+h+'" rx="3" fill="#6aa68d"><title>'+esc(num(lo+i*width,4)+'~'+num(lo+(i+1)*width,4)+' · '+counts[i]+'개 산업')+'</title></rect>';}
 svg+=svgText(64,66,'산업 수 (개)',11);
 for(let i=0;i<=4;i++)svg+=svgText(64+i*658/4,302,num(lo+(hi-lo)*i/4,2),10,'middle');
 svg+=svgText(393,325,d.name+' ('+d.unit+')',12,'middle');
 svg+='<path d="M'+px(s.low)+' 355H'+px(s.high)+' M'+px(s.low)+' 344V366 M'+px(s.high)+' 344V366" stroke="#3e6753" stroke-width="2"/><rect x="'+px(s.q1)+'" y="339" width="'+Math.max(1,px(s.q3)-px(s.q1))+'" height="32" fill="#d5e9df" stroke="#3e6753"/><path d="M'+px(s.median)+' 339V371" stroke="#1d6b50" stroke-width="3"/>';
 for(const r of valid)if(r[key]<s.low||r[key]>s.high)svg+=statsPoint(r.code,r.name,px(r[key]),355,'#9b7152',4,statsFormat(r[key],key)+' '+d.unit);
 svg+=svgText(393,398,'상자: Q1 '+num(s.q1,3)+' · 중앙값 '+num(s.median,3)+' · Q3 '+num(s.q3,3),11,'middle');
 const selected=statsRows.find(r=>r.code===statsSelected),value=selected?.[key];
 if(IOStats.finite(value)){
  const rank=1+valid.filter(r=>r[key]>value).length,pct=100*(valid.filter(r=>r[key]<value).length+valid.filter(r=>r[key]===value).length/2)/s.n;
  svg+='<path d="M'+px(value)+' 76V378" stroke="#b76b30" stroke-width="2" stroke-dasharray="5 4"/>'+svgText(393,435,selected.name+' · '+statsFormat(value,key)+' '+d.unit+' · 내림차순 '+rank+'/'+s.n+'위',12,'middle','#975122');
  $('stats-position').textContent=selected.name+'의 '+d.name+' 값은 '+statsFormat(value,key)+' '+d.unit+'입니다. 내림차순 '+rank+' / '+s.n+'위, 백분위 위치 '+num(pct,1)+'%입니다. '+(value>s.median?'중앙값보다 높습니다.':value<s.median?'중앙값보다 낮습니다.':'중앙값과 같습니다.')+' 백분위가 높을수록 값이 크며, 우수성이나 정책 우선순위를 뜻하지 않습니다.';
 }else $('stats-position').textContent=selected?selected.name+'에는 선택한 지표가 없습니다.':'검색에 맞는 산업이 없습니다. 전체 분포는 유지됩니다.';
 $('stats-distribution-chart').innerHTML=chartSVG(d.name+' · 분포와 상대적 위치',svg);bindStatPoints($('stats-distribution-chart'));
 $('stats-distribution-table').innerHTML=statsTable(['순위','코드','산업',d.name+' ('+d.unit+')'],valid.slice().sort((a,b)=>b[key]-a[key]).map(r=>[1+valid.filter(v=>v[key]>r[key]).length,r.code,r.name,statsFormat(r[key],key)]));
}
function relationNote(x,y){const pair=[x,y].sort().join('|');if(x===y)return '같은 지표의 자기상관입니다. 새로운 경제적 관계를 의미하지 않습니다.';if(pair===['backward','multiplier'].sort().join('|'))return '정의상 관계: 영향력계수는 생산유발계수(또는 산출 요구계수)를 평균으로 나눈 값입니다. 독립적인 발견이 아닙니다.';if(pair===['valueAddedRate','intermediateRate'].sort().join('|'))return '회계적 관계: 동일한 범위에서 총투입=중간투입+부가가치이면 두 비율의 합은 100%입니다. 강한 음의 상관은 회계적 정의에서 나타날 수 있습니다.';return '탐색적 관계입니다. 공통 분모·회계적 관계·산업 규모가 상관에 영향을 줄 수 있으며, 인과관계나 통계적 유의성을 판정하지 않습니다.';}
function heatColor(r){if(r===null)return '#f1f3f4';const end=r>=0?[29,107,80]:[69,104,162],t=Math.abs(r);return 'rgb('+end.map(c=>Math.round(248+(c-248)*t)).join(',')+')';}
function scatterSVG(points,xlabel,ylabel,title,size=false){
 const xr=axisRange(points.map(p=>p.x)),yr=axisRange(points.map(p=>p.y)),px=x=>72+(x-xr[0])/(xr[1]-xr[0])*632,py=y=>365-(y-yr[0])/(yr[1]-yr[0])*280;let svg='';
 for(let i=0;i<=4;i++){const x=72+i*632/4,y=365-i*280/4;svg+='<path d="M'+x+' 85V365 M72 '+y+'H704" stroke="#e7edeb"/>'+svgText(x,387,num(xr[0]+(xr[1]-xr[0])*i/4,2),10,'middle')+svgText(62,y+4,num(yr[0]+(yr[1]-yr[0])*i/4,2),10,'end');}
 svg+=svgText(72,65,ylabel,12)+svgText(388,414,xlabel,12,'middle');
 const outputMax=Math.max(1,...points.map(p=>IOStats.finite(p.output)?Math.max(0,p.output):0));
 const sorted=points.slice().sort((a,b)=>Number(a.code===statsSelected)-Number(b.code===statsSelected));
 for(const p of sorted){let radius=5;if(size&&IOStats.finite(p.output)&&p.output>0)radius=18*Math.sqrt(p.output/outputMax);svg+=statsPoint(p.code,p.name,px(p.x),py(p.y),p.color||'#287c64',Math.max(2,radius),num(p.x,4)+' / '+num(p.y,4)+(p.cluster===undefined?'':' · 군집 '+(p.cluster+1)));}
 const selected=points.find(p=>p.code===statsSelected);svg+=svgText(388,443,selected?selected.name+' · '+num(selected.x,4)+' / '+num(selected.y,4):'선택 산업이 유효 관측값에 포함되지 않습니다.',11,'middle');
 return chartSVG(title,svg);
}
function renderCorrelation(){
 const method=$('stats-corr-method').value,x=$('stats-x').value,y=$('stats-y').value,dx=statsDef(x),dy=statsDef(y);
 let html='<table><thead><tr><th>지표 / 지표</th>'+statsAvailable.map(k=>'<th title="'+esc(statsDef(k).definition)+'">'+esc(statsDef(k).name)+'</th>').join('')+'</tr></thead><tbody>';
 for(const a of statsAvailable){html+='<tr><th>'+esc(statsDef(a).name)+'</th>';for(const b of statsAvailable){const c=IOStats.correlation(statsRows.map(r=>r[a]),statsRows.map(r=>r[b]),method);html+='<td><button data-corr-x="'+a+'" data-corr-y="'+b+'" class="'+(a===x&&b===y?'chosen':'')+'" style="background:'+heatColor(c.r)+';color:'+(c.r!==null&&Math.abs(c.r)>.6?'#fff':'#273d32')+'" aria-label="'+esc(statsDef(a).name+' × '+statsDef(b).name+' '+(c.r===null?'계산 불가':num(c.r,3))+', '+c.n+'개 산업')+'">'+(c.r===null?'—':num(c.r,2))+'<small>n='+c.n+'</small></button></td>';}html+='</tr>';}
 $('stats-heatmap').innerHTML=html+'</tbody></table>';$('stats-heatmap').querySelectorAll('button').forEach(b=>b.onclick=()=>{$('stats-x').value=b.dataset.corrX;$('stats-y').value=b.dataset.corrY;renderCorrelation();});
 const pairs=statsRows.filter(r=>IOStats.finite(r[x])&&IOStats.finite(r[y])),c=IOStats.correlation(pairs.map(r=>r[x]),pairs.map(r=>r[y]),method);
 $('stats-correlation-summary').textContent=(method==='pearson'?'피어슨 r':'스피어만 ρ')+' = '+(c.r===null?'계산 불가 (산업 수 부족 또는 상수 지표)':num(c.r,4))+' · 유효 산업 '+c.n+'개 / '+statsRows.length+'개 · '+relationNote(x,y);
 $('stats-correlation-chart').innerHTML=pairs.length?scatterSVG(pairs.map(r=>({...r,x:r[x],y:r[y]})),dx.name+' ('+dx.unit+')',dy.name+' ('+dy.unit+')',dx.name+' × '+dy.name,$('stats-size').value==='output'):'<p class="empty-mini">두 지표가 모두 있는 산업이 없습니다.</p>';
 $('stats-correlation-note').textContent='산점도 축은 원래 지표값입니다. '+(method==='spearman'?'스피어만 상관계수는 동점에 평균순위를 적용해 계산합니다. ':'')+($('stats-size').value==='output'?'점 면적은 총산출에 비례합니다(최소 가시 반지름 2px; 0·결측은 고정 크기). 상관계수는 점 크기와 무관하게 동일 가중치입니다. ':'')+(c.n<10?'관측 산업 수가 적으므로 개별 산업에 결과가 크게 좌우될 수 있습니다.':'');
 bindStatPoints($('stats-correlation-chart'));
}
function invalidatePCA(){statsJob++;statsWorker?.terminate();statsWorker=null;statsPCA=null;statsRunning=false;$('stats-run-pca').disabled=false;$('stats-run-pca').textContent='산업 유형 분석하기';$('stats-pca-result').hidden=true;$('stats-pca-csv').disabled=$('stats-pca-svg').disabled=true;$('stats-pca-status').textContent='지표와 군집 수를 확인한 뒤 분석을 실행하세요.';$('stats-pca-status').classList.remove('analysis-warning');}
function runPCA(){
 if(!info?.ready||busy||statsRunning)return;
 invalidatePCA();const keys=Array.from($('stats-features').querySelectorAll('input:checked')).map(e=>e.value),job=++statsJob,version=loadVersion;
 statsRunning=true;$('stats-run-pca').disabled=true;$('stats-run-pca').textContent='계산 중…';$('stats-pca-status').textContent='표준화·주성분·군집을 계산하고 있습니다…';
 function finish(error,result){if(job!==statsJob||version!==loadVersion)return;statsRunning=false;$('stats-run-pca').disabled=false;$('stats-run-pca').textContent='산업 유형 분석하기';statsWorker?.terminate();statsWorker=null;if(error){$('stats-pca-status').textContent=error;$('stats-pca-status').classList.add('analysis-warning');return;}statsPCA=result;statsCluster=statsPCA.rows.find(r=>r.code===statsSelected)?.cluster||0;$('stats-pca-csv').disabled=$('stats-pca-svg').disabled=false;renderPCA();}
 try{statsWorker=new Worker('./stats-worker.js?v=20261117-stats2');statsWorker.onmessage=({data})=>finish(data.error,data.result);statsWorker.onerror=()=>finish('분석 엔진을 불러오지 못했습니다. 새로고침 후 다시 실행하세요.');statsWorker.postMessage({id:job,rows:statsRows,keys,k:Number($('stats-k').value)});}catch(e){finish(e.message);}
}
function renderPCA(){
 const r=statsPCA;if(!r)return;$('stats-pca-result').hidden=false;
 $('stats-pca-status').textContent='✓ 분석 완료 · '+r.n+'개 산업 · '+r.keys.length+'개 지표 · '+r.k+'개 군집 · 동일 가중치';
 $('stats-pca-summary').innerHTML=stat('두 축의 설명분산',num((r.explained[0]+r.explained[1])*100,1),'%','나머지 정보는 지도에 표시되지 않음')+stat('분석 산업',r.n,'개','결측 제외 '+r.excluded.length+'개')+stat('평균 실루엣',num(r.silhouette,3),'','−1~1 · 클수록 군집 분리')+stat('군집 수',r.k,'개','사용자가 설정 · 자동 최적값 아님');
 $('stats-pca-chart').innerHTML=scatterSVG(r.rows.map(p=>({...p,color:statsColors[p.cluster]})),'PC1 · '+num(r.explained[0]*100,1)+'%','PC2 · '+num(r.explained[1]*100,1)+'%','표준화 지표로 본 산업 유형');bindStatPoints($('stats-pca-chart'));
 $('stats-cluster-legend').innerHTML=r.clusters.map(g=>'<button data-stat-cluster="'+g.id+'" aria-pressed="'+(g.id===statsCluster)+'" class="'+(g.id===statsCluster?'stats-cluster-selected':'')+'"><span style="color:'+statsColors[g.id]+'">●</span> 군집 '+(g.id+1)+' · '+g.n+'개</button>').join('');$('stats-cluster-legend').querySelectorAll('button').forEach(b=>b.onclick=()=>{statsCluster=Number(b.dataset.statCluster);renderPCA();});
 const selected=r.rows.find(p=>p.code===statsSelected);$('stats-pca-position').textContent=selected?selected.name+'은 군집 '+(selected.cluster+1)+'에 속합니다. 아래 특성표는 선택한 군집 '+(statsCluster+1)+'의 평균입니다.': '선택 산업은 PCA의 완전 관측 산업에 포함되지 않았습니다.';
 const group=r.clusters[statsCluster],max=Math.max(1,...group.z.map(Math.abs));$('stats-cluster-profile').innerHTML=r.keys.map((key,j)=>{const z=group.z[j],w=Math.abs(z)/max*48;return '<div class="stats-cluster-row"><span>'+esc(statsDef(key).name)+'</span><div class="stats-z-track" title="평균 '+esc(statsFormat(group.means[j],key)+' '+statsDef(key).unit)+'"><i style="left:'+(z<0?50-w:50)+'%;width:'+w+'%;background:'+statsColors[statsCluster]+'"></i></div><b>'+num(z,2)+' σ</b></div>';}).join('')+'<p class="note">0은 분석 대상 전체 평균입니다. σ는 표준편차 단위이며 큰 값이 항상 좋은 것은 아닙니다.</p>';
 $('stats-loadings').innerHTML=statsTable(['지표','PC1과 상관(적재량)','PC2와 상관(적재량)'],r.loadings.map(l=>[statsDef(l.key).name,num(l.pc1,4),num(l.pc2,4)]));
 $('stats-pca-exclusions').textContent='지표 표준화: 표본 표준편차(분모 n−1). k-means++ 8회 초기화, 고정 시드 '+r.seed+'. 제거 지표: '+(r.omitted.map(o=>statsDef(o.key).name+' ('+o.reason+')').join(', ')||'없음')+'. 결측 제외 산업: '+(r.excluded.map(o=>o.code+' '+o.name).join(', ')||'없음')+'.';
 $('stats-pca-table').innerHTML=statsTable(['코드','산업','PC1','PC2','군집'],r.rows.map(o=>[o.code,o.name,num(o.x,4),num(o.y,4),o.cluster+1]));
}
function statsExport(which){
 if(!info?.ready)return;let rows=[...metadata(),['통계 범위','현재 자료 · 산업 동일 가중치 · 탐색적 분석'],['선택 산업',statsSelected],['분석 탭',which]];
 if(which==='distribution'){const k=$('stats-metric').value,d=statsDef(k),s=IOStats.describe(statsRows.map(r=>r[k]));rows.push(['지표',d.name],['단위',d.unit],['정의',d.definition],['구간',$('stats-bins').value],['사분위수','Type 7 선형 보간'],['표준편차','분모 n'],['유효 산업',s.n],['결측 제외',s.missing],['평균',s.mean],['중앙값',s.median],['표준편차',s.sd],['Q1',s.q1],['Q3',s.q3],['코드','산업',d.name]);rows.push(...statsRows.map(r=>[r.code,r.name,r[k]??'']));}
 if(which==='correlation'){const m=$('stats-corr-method').value;rows.push(['방법',m],['가로축',$('stats-x').value],['세로축',$('stats-y').value],['점 크기',$('stats-size').value],['결측 처리','지표 쌍별 제외; 상수 지표는 빈 값'],['해석',relationNote($('stats-x').value,$('stats-y').value)],['지표1','단위1','지표2','단위2','상관계수','유효 산업 수']);for(const a of statsAvailable)for(const b of statsAvailable){const c=IOStats.correlation(statsRows.map(r=>r[a]),statsRows.map(r=>r[b]),m);rows.push([statsDef(a).name,statsDef(a).unit,statsDef(b).name,statsDef(b).unit,c.r??'',c.n]);}rows.push([],['원자료 · 결측은 빈 값'],['코드','산업',...statsAvailable.map(k=>statsDef(k).name+' ('+statsDef(k).unit+')')],...statsRows.map(r=>[r.code,r.name,...statsAvailable.map(k=>r[k]??'')]));}
 if(which==='pca'){const r=statsPCA;if(!r)return;rows.push(['선택 지표',Array.from($('stats-features').querySelectorAll('input:checked')).map(e=>statsDef(e.value).name).join('; ')],['사용 지표',r.keys.map(k=>statsDef(k).name).join('; ')],['표준화','평균 0; 표본 표준편차 1'],['군집','전체 표준화 지표; k-means++; 8회 초기화'],['시드',r.seed],['군집 수',r.k],['평균 실루엣',r.silhouette],['PC1 설명분산',r.explained[0]],['PC2 설명분산',r.explained[1]],['코드','산업','PC1','PC2','군집'],...r.rows.map(o=>[o.code,o.name,o.x,o.y,o.cluster+1]),[],['지표','단위','표준화 평균','표준화 표준편차','PC1 적재량','PC2 적재량'],...r.loadings.map((l,i)=>[statsDef(l.key).name,statsDef(l.key).unit,r.means[i],r.sds[i],l.pc1,l.pc2]),[],['군집','산업 수',...r.keys.map(k=>statsDef(k).name+' 평균 z')],...r.clusters.map(g=>[g.id+1,g.n,...g.z]),[],['제외 지표','사유'],...r.omitted.map(o=>[statsDef(o.key).name,o.reason]),[],['결측 제외 코드','산업'],...r.excluded.map(o=>[o.code,o.name]));}
 downloadCSV('io-statistics-'+which+'-'+(info.meta.year||'data')+'.csv',rows);
}
function statsSVG(which){const svg=$('stats-'+(which==='pca'?'pca':which)+'-chart')?.querySelector('svg');if(!svg)return;const clone=svg.cloneNode(true);clone.querySelectorAll('[tabindex]').forEach(el=>{el.removeAttribute('tabindex');el.removeAttribute('role');});const details=document.createElementNS('http://www.w3.org/2000/svg','desc');details.textContent=JSON.stringify({metadata:metadata(),analysis:which,selected:statsSelected,metric:$('stats-metric').value,correlation:$('stats-corr-method').value,x:$('stats-x').value,y:$('stats-y').value,pointSize:$('stats-size').value,bins:$('stats-bins').value,pca:which==='pca'?{keys:statsPCA.keys,k:statsPCA.k,seed:statsPCA.seed,explained:statsPCA.explained,excluded:statsPCA.excluded,omitted:statsPCA.omitted}:null});clone.prepend(details);const blob=new Blob(['<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='io-statistics-'+which+'-'+(info.meta.year||'data')+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('stats-search').oninput=()=>{updateStatsSelection();renderStatistics();};$('stats-sector').onchange=()=>pickStats($('stats-sector').value);
for(const id of ['stats-metric','stats-bins'])$(id).onchange=renderDistribution;
for(const id of ['stats-x','stats-y','stats-corr-method','stats-size'])$(id).onchange=renderCorrelation;
$('stats-features').onchange=$('stats-k').onchange=invalidatePCA;$('stats-run-pca').onclick=runPCA;
$('stats-profile').onclick=()=>{if(statsSelected){showView('overview');history.replaceState(null,'','#overview');openProfile(statsSelected);}};
$('stats-scenario').onclick=()=>{if(statsSelected){$('scenario-search').value='';options($('scenario-sector'),info.sectors,statsSelected);showView('simulation');history.replaceState(null,'','#simulation');$('scenario-sector').focus();}};
document.querySelectorAll('[data-stats-tab]').forEach(b=>b.onclick=()=>{statsTab=b.dataset.statsTab;document.querySelectorAll('.stats-pane').forEach(p=>p.hidden=p.id!=='stats-pane-'+statsTab);document.querySelectorAll('[data-stats-tab]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});});
document.querySelectorAll('[data-stats-csv]').forEach(b=>b.onclick=()=>statsExport(b.dataset.statsCsv));document.querySelectorAll('[data-stats-svg]').forEach(b=>b.onclick=()=>statsSVG(b.dataset.statsSvg));
resetStatistics();
