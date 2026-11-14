/* Pure descriptive statistics; shared by the browser worker and Node checks. */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const quantile=(a,p)=>{if(!a.length)return null;const h=(a.length-1)*p,i=Math.floor(h);return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(h-i);};
function describe(values){
 const a=values.filter(finite).sort((a,b)=>a-b),n=a.length;
 if(!n)return {n:0,missing:values.length};
 const avg=mean(a),q1=quantile(a,.25),q3=quantile(a,.75),iqr=q3-q1,lo=q1-1.5*iqr,hi=q3+1.5*iqr;
 const inside=a.filter(v=>v>=lo&&v<=hi);
 return {n,missing:values.length-n,min:a[0],max:a[n-1],mean:avg,median:quantile(a,.5),q1,q3,iqr,sd:Math.sqrt(mean(a.map(v=>(v-avg)**2))),low:inside[0],high:inside.at(-1),outliers:a.filter(v=>v<lo||v>hi)};
}
function ranks(a){const sorted=a.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v),out=[];for(let i=0;i<a.length;){let j=i+1;while(j<a.length&&sorted[j].v===sorted[i].v)j++;for(let k=i;k<j;k++)out[sorted[k].i]=(i+j+1)/2;i=j;}return out;}
function correlation(x,y,method='pearson'){
 let pairs=x.map((v,i)=>[v,y[i]]).filter(r=>r.every(finite)),n=pairs.length;
 if(n<2)return {r:null,n};
 let a=pairs.map(r=>r[0]),b=pairs.map(r=>r[1]);
 if(method==='spearman'){a=ranks(a);b=ranks(b);}
 const ma=mean(a),mb=mean(b);let xx=0,yy=0,xy=0;
 for(let i=0;i<n;i++){const dx=a[i]-ma,dy=b[i]-mb;xx+=dx*dx;yy+=dy*dy;xy+=dx*dy;}
 return {r:xx>0&&yy>0?Math.max(-1,Math.min(1,xy/Math.sqrt(xx*yy))):null,n};
}
function eigenSymmetric(input){
 const n=input.length,a=input.map(r=>r.slice()),v=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>+(i===j)));
 for(let iter=0;iter<100*n*n;iter++){
  let p=0,q=1,max=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)if(Math.abs(a[i][j])>max){max=Math.abs(a[i][j]);p=i;q=j;}
  if(max<1e-12)break;
  const angle=.5*Math.atan2(2*a[p][q],a[q][q]-a[p][p]),c=Math.cos(angle),s=Math.sin(angle),ap=a[p][p],aq=a[q][q],off=a[p][q];
  for(let k=0;k<n;k++)if(k!==p&&k!==q){const x=a[k][p],y=a[k][q];a[k][p]=a[p][k]=c*x-s*y;a[k][q]=a[q][k]=s*x+c*y;}
  a[p][p]=c*c*ap-2*s*c*off+s*s*aq;a[q][q]=s*s*ap+2*s*c*off+c*c*aq;a[p][q]=a[q][p]=0;
  for(let k=0;k<n;k++){const x=v[k][p],y=v[k][q];v[k][p]=c*x-s*y;v[k][q]=s*x+c*y;}
 }
 const order=Array.from({length:n},(_,i)=>i).sort((i,j)=>a[j][j]-a[i][i]);
 const vectors=order.map(j=>{const col=v.map(r=>r[j]);const ix=col.reduce((best,x,i)=>Math.abs(x)>Math.abs(col[best])?i:best,0);return col.map(x=>x*(col[ix]<0?-1:1));});
 return {values:order.map(i=>Math.max(0,a[i][i])),vectors};
}
const distance=(a,b)=>a.reduce((s,x,j)=>s+(x-b[j])**2,0);
function kmeans(data,k){
 let best=null;
 for(let restart=0;restart<8;restart++){
  let seed=20261114+restart*101;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  let centers=[data[Math.floor(random()*data.length)].slice()];
  while(centers.length<k){const ds=data.map(r=>Math.min(...centers.map(c=>distance(r,c)))),sum=ds.reduce((a,b)=>a+b,0);let target=random()*sum,ix=ds.length-1;for(let i=0;i<ds.length;i++){target-=ds[i];if(target<0){ix=i;break;}}centers.push(data[ix].slice());}
  let labels=Array(data.length).fill(-1);
  for(let iter=0;iter<150;iter++){
   const next=data.map(r=>{let bi=0,bd=Infinity;centers.forEach((c,i)=>{const d=distance(r,c);if(d<bd){bd=d;bi=i;}});return bi;});
   if(next.every((v,i)=>v===labels[i]))break;labels=next;
   centers=centers.map((c,g)=>{const group=data.filter((_,i)=>labels[i]===g);if(group.length)return c.map((_,j)=>mean(group.map(r=>r[j])));const ds=data.map((r,i)=>distance(r,centers[labels[i]]));return data[ds.indexOf(Math.max(...ds))].slice();});
  }
  const inertia=data.reduce((s,r,i)=>s+distance(r,centers[labels[i]]),0);
  if(!best||inertia<best.inertia)best={labels,centers,inertia};
 }
 if(new Set(best.labels).size!==k)throw Error('선택한 군집 수로 구분할 수 없습니다. 군집 수를 줄이세요.');
 const groups=Array.from({length:k},(_,g)=>data.map((_,i)=>i).filter(i=>best.labels[i]===g));
 best.silhouette=mean(data.map((r,i)=>{const own=best.labels[i];if(groups[own].length===1)return 0;const av=groups.map((group,g)=>group.reduce((s,j)=>s+(j===i?0:Math.sqrt(distance(r,data[j]))),0)/(group.length-(g===own?1:0)));const a=av[own],b=Math.min(...av.filter((_,g)=>g!==own));return Math.max(a,b)>0?(b-a)/Math.max(a,b):0;}));
 return best;
}
function pcaCluster(rows,requested,k){
 if(!Array.isArray(requested)||requested.length<2)throw Error('서로 다른 지표를 2개 이상 선택하세요.');
 requested=[...new Set(requested)];
 const complete=rows.filter(r=>requested.every(key=>finite(r[key]))),n=complete.length;
 if(n<3)throw Error('선택한 모든 지표가 있는 산업이 3개 이상 필요합니다. 지표 선택 또는 자료 연결을 확인하세요.');
 const keys=[],means=[],sds=[],zcols=[],omitted=[];
 for(const key of requested){
  const col=complete.map(r=>r[key]),avg=mean(col),sd=Math.sqrt(col.reduce((s,x)=>s+(x-avg)**2,0)/(n-1));
  if(!(sd>1e-12*Math.max(1,...col.map(Math.abs)))){omitted.push({key,reason:'변동 없음 또는 수치적으로 매우 작은 변동'});continue;}
  const z=col.map(x=>(x-avg)/sd);const duplicate=zcols.findIndex(c=>Math.abs(correlation(c,z).r)>1-1e-10);
  if(duplicate>=0){omitted.push({key,reason:keys[duplicate]+'와 완전한 선형 관계'});continue;}
  keys.push(key);means.push(avg);sds.push(sd);zcols.push(z);
 }
 if(keys.length<2)throw Error('상수·완전 선형 중복 지표를 제외하면 2개 미만입니다. 다른 지표를 선택하세요.');
 const z=complete.map((_,i)=>zcols.map(c=>c[i])),p=keys.length;
 const cov=Array.from({length:p},(_,i)=>Array.from({length:p},(_,j)=>zcols[i].reduce((s,x,t)=>s+x*zcols[j][t],0)/(n-1)));
 const eig=eigenSymmetric(cov),total=eig.values.reduce((a,b)=>a+b,0),unique=new Set(z.map(r=>r.join(','))).size;
 if(!Number.isInteger(k)||k<2||k>Math.min(6,n-1,unique))throw Error('군집 수는 2~'+Math.min(6,n-1,unique)+' 사이여야 합니다. 산업 수와 서로 다른 관측값을 확인하세요.');
 const km=kmeans(z,k),scores=z.map(r=>eig.vectors.slice(0,2).map(v=>r.reduce((s,x,j)=>s+x*v[j],0)));
 const groupOrder=Array.from({length:k},(_,g)=>g).sort((a,b)=>mean(scores.filter((_,i)=>km.labels[i]===a).map(r=>r[0]))-mean(scores.filter((_,i)=>km.labels[i]===b).map(r=>r[0])));
 return {n,total:rows.length,keys,means,sds,omitted,excluded:rows.filter(r=>!complete.includes(r)).map(r=>({code:r.code,name:r.name})),eigenvalues:eig.values,explained:eig.values.map(v=>v/total),vectors:eig.vectors,loadings:keys.map((key,j)=>({key,pc1:eig.vectors[0][j]*Math.sqrt(eig.values[0]),pc2:eig.vectors[1][j]*Math.sqrt(eig.values[1])})),rows:complete.map((r,i)=>({code:r.code,name:r.name,x:scores[i][0],y:scores[i][1],cluster:groupOrder.indexOf(km.labels[i])})),clusters:groupOrder.map((g,id)=>({id,n:km.labels.filter(v=>v===g).length,z:km.centers[g],means:km.centers[g].map((x,j)=>x*sds[j]+means[j])})),silhouette:km.silhouette,inertia:km.inertia,k,seed:20261114,restarts:8};
}
const api={finite,mean,quantile,describe,ranks,correlation,eigenSymmetric,pcaCluster};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.IOStats=api;
})(typeof self!=='undefined'?self:globalThis);
