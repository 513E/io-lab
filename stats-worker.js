'use strict';
importScripts('./stats-math.js?v=20261117-stats2');
onmessage=({data})=>{try{postMessage({id:data.id,result:IOStats.pcaCluster(data.rows,data.keys,data.k)});}catch(e){postMessage({id:data.id,error:e.message});}};
