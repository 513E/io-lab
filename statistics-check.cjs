const assert=require('node:assert/strict');
const S=require('./stats-math.js');
const close=(a,b,tol=1e-9)=>assert.ok(Math.abs(a-b)<tol,`${a} != ${b}`);
let checks=0;
function test(name,f){f();checks++;console.log('PASS',name);}
test('Type 7 quartiles, population SD, missing is not zero',()=>{const s=S.describe([1,2,3,4,null,undefined,NaN]);assert.equal(s.n,4);assert.equal(s.missing,3);close(s.q1,1.75);close(s.median,2.5);close(s.q3,3.25);close(s.sd,Math.sqrt(1.25));});
test('Constant and singleton distributions',()=>{const s=S.describe([2,2,2]);assert.equal(s.sd,0);assert.equal(s.low,2);assert.equal(S.describe([1]).median,1);assert.equal(S.describe([null]).n,0);});
test('Ties use average ranks; pairwise deletion; constant correlation',()=>{assert.deepEqual(S.ranks([10,20,20,40]),[1,2.5,2.5,4]);close(S.correlation([1,2,3,null],[3,2,1,100]).r,-1);assert.equal(S.correlation([1,1],[2,3]).r,null);close(S.correlation([1,2,2,4],[10,30,30,100],'spearman').r,1);});
test('Known symmetric eigendecomposition',()=>{let e=S.eigenSymmetric([[2,1],[1,2]]);close(e.values[0],3);close(e.values[1],1);close(Math.abs(e.vectors[0][0]),Math.SQRT1_2);});
const sample=Array.from({length:30},(_,i)=>({code:String(i),name:'산업'+i,a:(i<15?-10:10)+Math.sin(i),b:(i<15?-4:5)+Math.cos(i),c:Math.sin(i*.8),duplicate:((i<15?-10:10)+Math.sin(i))*2,constant:1}));
test('PCA orthogonality, eigen residual, scores and deterministic clusters',()=>{const r=S.pcaCluster(sample,['a','b','c'],2),r2=S.pcaCluster(sample,['a','b','c'],2);assert.deepEqual(r,r2);close(r.explained.reduce((a,b)=>a+b),1);close(r.eigenvalues.reduce((a,b)=>a+b),3);assert.deepEqual(r.clusters.map(g=>g.n).sort(),[15,15]);assert.ok(r.silhouette>.4);for(let i=0;i<3;i++)for(let j=0;j<3;j++)close(r.vectors[i].reduce((s,x,k)=>s+x*r.vectors[j][k],0),+(i===j));});
test('Complete-case deletion, redundant and constant features',()=>{const rows=[...sample,{code:'missing',a:null,b:5,c:0,duplicate:10,constant:1}],r=S.pcaCluster(rows,['a','b','c','duplicate','constant'],2);assert.equal(r.n,30);assert.equal(r.excluded[0].code,'missing');assert.equal(r.omitted.length,2);assert.deepEqual(r.keys,['a','b','c']);});
test('Insufficient data and invalid cluster counts rejected',()=>{assert.throws(()=>S.pcaCluster(sample.slice(0,2),['a','b'],2));assert.throws(()=>S.pcaCluster(sample,['constant','a','duplicate'],2));assert.throws(()=>S.pcaCluster(sample,['a','b'],0));});
console.log(`${checks} tests passed`);
