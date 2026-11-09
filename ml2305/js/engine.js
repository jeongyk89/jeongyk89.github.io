import {decodeYOLO, poseSummary} from './core.js';

const assets = new URL('../assets/', import.meta.url);
const asset = path => new URL(path, assets).href;
export class ModelError extends Error {
  constructor(stage, detail, url='') { super(detail); this.name='ModelError'; this.stage=stage; this.url=url; }
}
async function bytes(path, label, progress) {
  const url=asset(path);
  let response;
  const timeout=new AbortController();
  const timer=setTimeout(()=>timeout.abort(),120000);
  try {
    try { response=await fetch(url,{signal:timeout.signal,cache:'default'}); }
    catch(e) { throw new ModelError('download',`${label}: ${e.name==='AbortError'?'download timed out':'network request failed'}.`,url); }
    if(!response.ok) throw new ModelError('download',`${label}: HTTP ${response.status}. The complete model/assets folder must be published.`,url);
    if((response.headers.get('content-type')||'').includes('text/html')) throw new ModelError('download',`${label}: the server returned an HTML page instead of model data.`,url);
    const total=Number(response.headers.get('content-length'))||0;
    if(!response.body) return new Uint8Array(await response.arrayBuffer());
    const reader=response.body.getReader(),chunks=[];let size=0,last=0;
    while(true){const {done,value}=await reader.read();if(done)break;chunks.push(value);size+=value.length;
      if(performance.now()-last>250){progress(`Loading ${label}… ${(size/1e6).toFixed(1)}${total?' / '+(total/1e6).toFixed(1):''} MB`);last=performance.now();}}
    const joined=new Uint8Array(size);let offset=0;for(const chunk of chunks){joined.set(chunk,offset);offset+=chunk.length;}
    return joined;
  } catch(e) {
    if(e instanceof ModelError)throw e;
    throw new ModelError('download',`${label}: download did not complete. ${e.message}`,url);
  } finally { clearTimeout(timer); }
}
function script(path) {
  const url=asset(path);
  return new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=url;
    const timer=setTimeout(()=>{s.remove();reject(new ModelError('runtime','Runtime download timed out.',url));},60000);
    s.onload=()=>{clearTimeout(timer);resolve();};s.onerror=()=>{clearTimeout(timer);s.remove();reject(new ModelError('runtime','Could not load the detector runtime. Check the published assets folder.',url));};document.head.append(s);});
}

export async function createEngine(station, progress=()=>{}) {
  if(station==='objects'){
    progress('Loading detector…');
    if(!window.ort) await script('vendor/onnx/ort.wasm.min.js');
    const ort=window.ort;
    if(!ort) throw new ModelError('runtime','The detector runtime did not initialise.');
    ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false;ort.env.wasm.wasmPaths=asset('vendor/onnx/');
    const model=await bytes('models/yolo26n.onnx','object model',progress);
    progress('Preparing detector…');
    let session;
    try{session=await ort.InferenceSession.create(model,{executionProviders:['wasm'],graphOptimizationLevel:'all'});}
    catch(e){throw new ModelError('initialisation',`Detector/WASM initialisation failed: ${e.message}`,asset('vendor/onnx/'));}
    const canvas=document.createElement('canvas');canvas.width=640;canvas.height=640;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    return {name:'YOLO26n · COCO 80', async analyze(image,{threshold=.35}={}){
      const w=image.width,h=image.height,scale=Math.min(640/w,640/h),nw=Math.round(w*scale),nh=Math.round(h*scale),padX=Math.floor((640-nw)/2),padY=Math.floor((640-nh)/2);
      ctx.fillStyle='rgb(114,114,114)';ctx.fillRect(0,0,640,640);ctx.drawImage(image,padX,padY,nw,nh);
      const rgba=ctx.getImageData(0,0,640,640).data,n=640*640,input=new Float32Array(n*3);
      for(let i=0;i<n;i++){input[i]=rgba[4*i]/255;input[n+i]=rgba[4*i+1]/255;input[n*2+i]=rgba[4*i+2]/255;}
      const tensor=new ort.Tensor('float32',input,[1,3,640,640]);let output;
      try{output=await session.run({[session.inputNames[0]]:tensor});const raw=output[session.outputNames[0]];
        return {detections:decodeYOLO(raw.data,raw.dims,threshold,{scale,padX,padY,width:w,height:h})};}
      finally{tensor.dispose?.();if(output)Object.values(output).forEach(t=>t.dispose?.());}
    }};
  }
  if(station!=='pose') throw new Error('Unknown station.');
  progress('Loading pose tracker…');
  let api,fileset,pose;
  try{api=await import(asset('vendor/mediapipe/vision_bundle.mjs'));fileset=await api.FilesetResolver.forVisionTasks(asset('vendor/mediapipe/wasm'));}
  catch(e){throw new ModelError('runtime',`Could not load the pose runtime: ${e.message}`,asset('vendor/mediapipe/'));}
  const model=await bytes('models/pose_landmarker_lite.task','pose model',progress);
  progress('Preparing pose tracker…');
  try{pose=await api.PoseLandmarker.createFromOptions(fileset,{baseOptions:{modelAssetBuffer:model,delegate:'CPU'},runningMode:'IMAGE',numPoses:1,minPoseDetectionConfidence:.5,minPosePresenceConfidence:.5,minTrackingConfidence:.5});}
  catch(e){throw new ModelError('initialisation',`Pose/WASM initialisation failed: ${e.message}`,asset('vendor/mediapipe/wasm/'));}
  let mode='IMAGE';
  return {name:'MediaPipe Pose Lite · one person',async analyze(image,{video=false}={}){
    const desired=video?'VIDEO':'IMAGE';if(desired!==mode){await pose.setOptions({runningMode:desired});mode=desired;}
    const result=video?pose.detectForVideo(image,performance.now()):pose.detect(image);
    const points=result.landmarks?.[0]||null;
    return {points,metrics:poseSummary(points,image.width,image.height)};
  }};
}
