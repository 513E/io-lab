const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const math=fs.readFileSync('stats-math.js','utf8');
const ui=fs.readFileSync('statistics.js','utf8').split('function updateStatsSelection(){')[0];
for(const commonJS of [false,true]){
 const context=vm.createContext(commonJS?{module:{exports:{}}}:{});
 context.self=context;
 vm.runInContext(math,context);
 assert.equal(context.IOStats.describe([1,3]).mean,2);
 if(commonJS)assert.equal(context.module.exports,context.IOStats);
}
console.log('PASS global API remains available with and without CommonJS');
async function checkLoading(mode){
 const elements=new Map(),element=()=>({hidden:false,textContent:'',value:'',children:[],replaceChildren(){this.children=[];},appendChild(x){this.children.push(x);},remove(){}});
 const info={ready:true};
 const context=vm.createContext({info,loadVersion:1,console:{warn(){}},setTimeout,clearTimeout,$:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}});
 context.document={createElement:element,head:{appendChild(script){queueMicrotask(()=>{if(mode==='failure')script.onerror();else {vm.runInContext(math,context);script.onload();}});}}};
 vm.runInContext(ui+'\npopulateStatistics=()=>{globalThis.populated=true;};',context);
 await vm.runInContext('refreshStatistics()',context);
 assert.equal(context.info,info,'The loaded dataset must survive statistics initialization');
 if(mode==='failure'){
  assert.equal(elements.get('stats-workspace').hidden,true);
  assert.match(elements.get('stats-empty').textContent,/유지됩니다/);
  assert.equal(elements.get('stats-empty').children[0].textContent,'통계 다시 연결');
  vm.runInContext(math,context);
  await elements.get('stats-empty').children[0].onclick();
 }
 assert.equal(context.populated,true);
}
(async()=>{await checkLoading('success');console.log('PASS missing dependency reloads before statistics initialization');await checkLoading('failure');console.log('PASS dependency failure preserves data and retry recovers');})().catch(e=>{console.error(e);process.exitCode=1;});
