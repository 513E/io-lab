'use strict';
function compareClassifications(coarse,fine,pairs,group,weight='output',confirmed=false){
 if(!coarse||!fine)throw Error('집계 자료 A와 세부 자료 B를 먼저 저장하세요.');
 if(coarse.n>=fine.n)throw Error('A는 산업 수가 적은 집계 분류, B는 산업 수가 많은 세부 분류로 지정하세요.');
 for(const key of ['year','price','unit','modelBasis']){const a=coarse.meta[key],b=fine.meta[key];if(a!==b)throw Error('두 자료의 '+({year:'연도',price:'기준가격',unit:'금액 단위',modelBasis:'모형 기준'}[key])+'가 다릅니다. 동일 조건의 자료를 사용하세요.');}
 if((!coarse.meta.year||!coarse.meta.price||coarse.meta.price==='기준가격 미지정')&&!confirmed)throw Error('연도·가격 정보가 비어 있습니다. 동일 기준 자료인지 확인해 주세요.');
 const cs=new Set(coarse.sectors.map(s=>s.code)),fs=new Set(fine.sectors.map(s=>s.code)),mapping=new Map();
 for(const p of pairs){if(!cs.has(p.coarse_code)||!fs.has(p.fine_code))throw Error('연결표에 현재 자료에 없는 산업 코드가 있습니다.');if(mapping.has(p.fine_code))throw Error('세부 산업 코드가 중복 연결되었습니다.');mapping.set(p.fine_code,p.coarse_code);}
 if(mapping.size!==fine.n)throw Error('모든 세부 산업을 집계 산업에 한 번씩 연결해야 합니다.');
 if(new Set(mapping.values()).size!==coarse.n)throw Error('연결되지 않은 집계 산업이 있습니다.');
 const parent=coarse.sectors.find(s=>s.code===group);if(!parent)throw Error('비교할 산업을 선택하세요.');
 const children=fine.sectors.filter(s=>mapping.get(s.code)===group);
 if(!children.length)throw Error('연결된 세부 산업이 없습니다.');
 if(weight==='output'&&children.some(s=>s.output===null||!Number.isFinite(s.output)||s.output<0))throw Error('산출액 비중 배분에는 세부 산업 총산출이 필요합니다.');
 const denom=weight==='equal'?children.length:children.reduce((a,s)=>a+s.output,0);if(!(denom>0))throw Error('세부 산업 총산출의 합계가 0입니다. 산출 비중을 정할 수 없으므로 균등 배분을 선택하거나 다른 산업을 비교하세요.');
 const details=children.map(s=>({...s,weight:(weight==='equal'?1:s.output)/denom}));
 const rows=['multiplier','vaMultiplier','importMultiplier'].map(k=>{const a=parent[k],b=details.every(s=>s[k]!==null&&Number.isFinite(s[k]))?details.reduce((sum,s)=>sum+s.weight*s[k],0):null;return {key:k,coarse:a,fine:b,difference:a===null||b===null?null:b-a};});
 return {group:parent,details,rows,weight,coarseName:coarse.name,fineName:fine.name};
}
if(typeof module!=='undefined')module.exports={compareClassifications};
