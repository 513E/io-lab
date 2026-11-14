'use strict';
importScripts('./stats-math.js');
onmessage=({data})=>{try{postMessage({id:data.id,result:IOStats.pcaCluster(data.rows,data.keys,data.k)});}catch(e){postMessage({id:data.id,error:e.message});}};
