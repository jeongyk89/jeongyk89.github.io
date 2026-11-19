import {LABELS,Tracker,csv} from './core.js';
import {createEngine,ModelError} from './engine.js';
const $=id=>document.getElementById(id),station=document.body.dataset.station,isObject=station==='objects';
const video=$('video'),photo=$('photo'),overlay=$('overlay'),pen=overlay.getContext('2d'),still=$('still');
const sample=document.createElement('canvas'),samplePen=sample.getContext('2d',{willReadFrequently:true});
const completed=document.createElement('canvas'),completedPen=completed.getContext('2d');
let epoch=0,stream=null,running=false,busy=false,starting=false,source='none',engine=null,loading=null,timer=null,last=null,photoURL=null,pendingPhoto=false;
const tracker=new Tracker(),encounters=new Map(),key='ML2305:'+station+':trials';
let trials=[];try{const saved=JSON.parse(sessionStorage.getItem(key)||'[]');if(Array.isArray(saved))trials=saved.slice(-1000);}catch{}
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
function clearError(){$('error-help').hidden=true;$('retry').hidden=true;}
function error(e,kind='model'){
  let message;
  if(kind==='camera'){
    if(e.name==='NotAllowedError')message='Camera access was denied. Allow it in your browser, or choose a photo.';
    else if(e.name==='NotFoundError')message='No camera found. Choose a photo instead.';
    else if(e.name==='NotReadableError')message='Camera is busy. Close other camera apps and try again.';
    else message='Camera could not start. Try again or choose a photo.';
  }else message=e.stage==='download'||e.stage==='runtime'?'Model files could not load. Try again; if it continues, tell Jake.':'The model could not run on this device. Try a smaller photo or another browser.';
  status(message,true);$('error-detail').textContent=[e.message,e.url].filter(Boolean).join(' ');$('error-help').hidden=false;$('retry').hidden=false;
}
function text(tag,value,cls){const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;}
function saveState(){try{sessionStorage.setItem(key,JSON.stringify(trials));}catch{}$('trial-count').textContent=trials.length+' saved';$('export').disabled=!trials.length;}
function invalidateResult(){last=null;$('save').disabled=true;$('speed').textContent='';pen.clearRect(0,0,overlay.width,overlay.height);$('metric').replaceChildren(document.createTextNode('—'),text('small',isObject?'objects in this frame':'of 12 body joints visible'));$('results').replaceChildren(text('p','No result yet.','empty-result'));document.body.dataset.inference='pending';delete document.body.dataset.resultCount;}
function stop({freeze=true,message=''}={}){
  epoch++;running=false;starting=false;clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;video.hidden=true;
  $('start').disabled=false;$('stop').disabled=true;
  if(freeze&&last&&source==='camera'){
    still.width=completed.width;still.height=completed.height;still.getContext('2d').drawImage(completed,0,0);still.hidden=false;photo.hidden=true;$('empty').hidden=true;
  }else if(source==='camera'){still.hidden=true;$('empty').hidden=false;}
  if(message)status(message);
}
async function getEngine(g){
  if(engine)return engine;
  if(!loading)loading=createEngine(station,msg=>{if(g===epoch)status(msg);}).then(value=>{engine=value;return value;}).catch(e=>{loading=null;throw e;});
  return loading;
}
function capture(input){
  const w=input.videoWidth||input.naturalWidth||input.width,h=input.videoHeight||input.naturalHeight||input.height;
  if(!w||!h)throw new Error('Image dimensions are not available yet.');
  const scale=Math.min(1,1280/Math.max(w,h));sample.width=Math.round(w*scale);sample.height=Math.round(h*scale);samplePen.drawImage(input,0,0,sample.width,sample.height);
  return sample;
}
function drawBoxes(ds,w,h){
  pen.clearRect(0,0,w,h);const size=Math.max(14,w/55);pen.font=`600 ${size}px system-ui`;pen.lineWidth=Math.max(2,w/350);
  for(const d of ds){pen.strokeStyle='#c9f58d';pen.strokeRect(d.x,d.y,d.w,d.h);const label=`${d.label} ${Math.round(d.score*100)}%${d.id?' #'+d.id:''}`;const y=Math.max(size+8,d.y);pen.fillStyle='#c9f58d';pen.fillRect(d.x,y-size-7,pen.measureText(label).width+12,size+8);pen.fillStyle='#102721';pen.fillText(label,d.x+5,y-4);}
}
const connections=[[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[27,29],[29,31],[28,30],[30,32]];
function drawPose(points,w,h){
  pen.clearRect(0,0,w,h);if(!points)return;pen.lineWidth=Math.max(3,w/220);pen.strokeStyle='#c9f58d';
  for(const [a,b] of connections){if((points[a]?.visibility||0)<.6||(points[b]?.visibility||0)<.6)continue;pen.beginPath();pen.moveTo(points[a].x*w,points[a].y*h);pen.lineTo(points[b].x*w,points[b].y*h);pen.stroke();}
  for(const p of points.slice(11)){if((p.visibility||0)<.6)continue;pen.fillStyle='white';pen.beginPath();pen.arc(p.x*w,p.y*h,Math.max(4,w/160),0,Math.PI*2);pen.fill();}
}
function showObjects(ds){
  $('metric').replaceChildren(document.createTextNode(String(ds.length)),text('small','objects in this frame'));$('results').replaceChildren();
  const counts={};for(const d of ds){counts[d.label]=(counts[d.label]||0)+1;const row=text('div','','result-row');row.append(text('span',d.label+(d.id?' #'+d.id:'')),text('small',Math.round(d.score*100)+'%'));$('results').append(row);}
  if(!ds.length)$('results').append(text('p','No detections above this confidence threshold.','empty-result'));
  for(const [name,count] of Object.entries(counts))encounters.set(name,Math.max(count,encounters.get(name)||0));
  $('encounters').replaceChildren();for(const [name,count] of [...encounters].sort())$('encounters').append(text('span',name+' · max '+count,'chip'));
}
function showPose(points,m){
  $('metric').replaceChildren(document.createTextNode(`${Math.round(m.visible*12)}/12`),text('small','body joints visible (visibility ≥ 0.60)'));
  $('results').replaceChildren();const grid=text('div','','angles');
  for(const [title,k] of [['Left elbow','leftElbow'],['Right elbow','rightElbow'],['Left knee','leftKnee'],['Right knee','rightKnee']]){const box=document.createElement('div');box.append(text('strong',m[k]===null?'—':Math.round(m[k])+'°'),text('span',title));grid.append(box);}
  $('results').append(grid);if(!points)$('results').append(text('p','No pose found. Try a clearer view of one person.','empty-result'));
}
async function analyze(input,live=false){
  if(busy){if(!live)pendingPhoto=true;return;}busy=true;const g=epoch,threshold=Number($('confidence')?.value||.35);
  try{
    const active=await getEngine(g);if(g!==epoch)return;
    const frame=capture(input),start=performance.now(),result=await active.analyze(frame,{video:live,threshold});
    if(g!==epoch)return;
    const elapsed=performance.now()-start,w=frame.width,h=frame.height;overlay.width=w;overlay.height=h;
    completed.width=w;completed.height=h;completedPen.drawImage(frame,0,0);
    if(isObject){const ds=live?tracker.update(result.detections):result.detections;drawBoxes(ds,w,h);showObjects(ds);
      last={station:'Objects',model:'YOLO26n COCO80',source,confidence:threshold,detected:ds.length,labels:ds.map(d=>`${d.label}:${d.score.toFixed(3)}${d.id?' #'+d.id:''}`).join('; ')};
    }else{drawPose(result.points,w,h);showPose(result.points,result.metrics);const m=result.metrics;
      last={station:'Pose',model:'MediaPipe Pose Lite 0.10.21',source,detected:result.points?1:0,visible_of_12:Math.round(m.visible*12),left_elbow_2d:m.leftElbow??'',right_elbow_2d:m.rightElbow??'',left_knee_2d:m.leftKnee??'',right_knee_2d:m.rightKnee??''};}
    Object.assign(last,{analysed_at:new Date().toISOString(),inference_ms:Math.round(elapsed),width:w,height:h});
    $('speed').textContent=`${Math.round(elapsed)} ms per inference`;$('save').disabled=isObject&&threshold!==Number($('confidence').value);clearError();
    document.body.dataset.inference='ready';document.body.dataset.resultCount=String(last.detected);
    status(live?'Camera running.':'Photo analysed.');
  }catch(e){if(g===epoch){stop();error(e);document.body.dataset.inference='error';}}
  finally{busy=false;if(pendingPhoto&&source==='photo'&&!running){pendingPhoto=false;analyze(photo);}}
}
async function camera(){
  stop({freeze:false});invalidateResult();clearError();source='camera';photo.hidden=true;still.hidden=true;tracker.reset();
  const g=epoch;starting=true;$('start').disabled=true;$('stop').disabled=false;
  try{
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw new Error('Open the published HTTPS page in Safari or Chrome. Camera access is unavailable in this preview.');
    status('Allow camera access…');
    const acquired=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:$('facing').value},width:{ideal:960},height:{ideal:720}}});
    if(g!==epoch||document.hidden){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;video.srcObject=acquired;await video.play();
    if(g!==epoch||document.hidden){acquired.getTracks().forEach(t=>t.stop());return;}
    video.hidden=false;$('empty').hidden=true;running=true;starting=false;status('Camera ready. Loading model…');
    const loop=async()=>{if(g!==epoch||!running)return;if(video.readyState>=2)await analyze(video,true);if(g===epoch&&running)timer=setTimeout(loop,120);};loop();
  }catch(e){if(g===epoch){stop({freeze:false});error(e,'camera');}}
}
function choosePhoto(file){
  if(!file)return;if(file.size>30*1024*1024){status('Choose a photo smaller than 30 MB.',true);return;}
  stop({freeze:false});invalidateResult();clearError();source='photo';pendingPhoto=false;tracker.reset();const g=epoch;
  if(photoURL)URL.revokeObjectURL(photoURL);photoURL=URL.createObjectURL(file);
  photo.onload=()=>{if(g!==epoch||source!=='photo')return;photo.hidden=false;still.hidden=true;video.hidden=true;$('empty').hidden=true;status('Photo ready. Loading model…');analyze(photo);};
  photo.onerror=()=>{if(g===epoch)status('This image could not open. Try JPEG or PNG.',true);};photo.src=photoURL;
}
$('start').onclick=camera;$('stop').onclick=()=>stop({message:'Stopped. The last analysed frame is shown.'});
$('facing').onchange=()=>{if(running||starting)camera();};
$('upload').onchange=e=>{choosePhoto(e.target.files[0]);e.target.value='';};
$('retry').onclick=()=>{clearError();if(source==='photo'&&photo.complete)analyze(photo);else camera();};
if(isObject){$('class-list').textContent=LABELS.join(', ');$('reset-encounters').onclick=()=>{tracker.reset();encounters.clear();$('encounters').replaceChildren();};
  let debounce;$('confidence').oninput=()=>{$('confidence-value').textContent=Number($('confidence').value).toFixed(2);$('save').disabled=true;clearTimeout(debounce);if(source==='photo')debounce=setTimeout(()=>analyze(photo),180);};}
$('save').onclick=()=>{if(!last)return;trials.push({...last,recorded_at:new Date().toISOString(),condition:$('condition').value,manual_expected:$('expected').value,mismatch:$('mismatch').value,notes:$('notes').value});trials=trials.slice(-1000);saveState();$('trial-toast').textContent='Trial saved.';};
$('export').onclick=()=>{const blob=new Blob(['\ufeff'+csv(trials)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`ML2305_${station}_${new Date().toISOString().slice(0,10)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&(source==='camera'||starting||running)){pendingPhoto=false;stop({message:'Paused. Press Start camera to resume.'});}});
window.addEventListener('pagehide',()=>{pendingPhoto=false;stop();});saveState();
if(location.protocol==='file:')status('Open this page from your published GitHub Pages site. Local preview cannot load the models.',true);
