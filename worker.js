const ROOT='https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
let py, ready=false, queue=Promise.resolve();
async function handle({id,type,payload}){
  try{
    if(!ready){
      postMessage({status:'분석 엔진을 준비하고 있습니다. 첫 실행에는 시간이 걸릴 수 있습니다.'});
      importScripts(ROOT+'pyodide.js');
      py=await loadPyodide({indexURL:ROOT});
      await py.loadPackage(['numpy','micropip']);
      await py.runPythonAsync("import micropip\nawait micropip.install('openpyxl==3.1.5')");
      const extension=await fetch('./advanced.py');
      if(!extension.ok)throw Error('심화 분석 코드를 불러오지 못했습니다.');
      py.FS.writeFile('/home/pyodide/advanced.py',await extension.text());
      const response=await fetch('./model.py');
      if(!response.ok) throw Error('분석 코드를 불러오지 못했습니다.');
      await py.runPythonAsync(await response.text());
      ready=true;
    }
    let answer;
    if(type==='load'){
      postMessage({status:'Excel의 모든 시트를 읽고 계산식을 검증하고 있습니다…'});
      py.globals.set('js_bytes',new Uint8Array(payload.buffer));
      py.globals.set('js_filename',payload.filename||'');
   answer=await py.runPythonAsync('initialize(js_bytes.to_py(), js_filename)');
   py.globals.delete('js_filename');
      py.globals.delete('js_bytes');
    } else {
      py.globals.set('method_name',type);py.globals.set('method_payload',JSON.stringify(payload));
      answer=py.runPython('dispatch(method_name, method_payload)');
    }
    postMessage({id,result:JSON.parse(answer)});
  }catch(error){postMessage({id,error:String(error)});}
}
onmessage=e=>{queue=queue.then(()=>handle(e.data));};
