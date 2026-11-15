/* Native, skippable orbital boot. Uses the existing live map and original spacecraft mesh. */
(() => {
 'use strict';
 const intro=document.getElementById('satellite-intro'),button=document.getElementById('intro-skip'),status=document.getElementById('intro-status');
 if(!intro)return;
 const query=new URLSearchParams(location.search),key='seamline-native-intro-v1';
 let seen=false;try{seen=sessionStorage.getItem(key)==='seen';}catch(_){seen=true;}
 let closed=true,manual=false,skipped=false,started=0,frame=0,clock=0,previous=null,backup=null,ready=false,scanStarted=false,descentStarted=false;
 const full=()=>window.Seam?Seam.motionMode()==='full':!matchMedia('(prefers-reduced-motion: reduce)').matches&&!['off','reduced'].includes(document.documentElement.dataset.motion);
 const background=()=>document.querySelectorAll('#top,#main,#navigation-drawer,#navigation-shade');
 function draw(now){
  if(closed||document.hidden)return;
  const model=window.SeamSatelliteModels?.models.get('Terra'),host=document.getElementById('intro-model');
  if(model){
   let canvas=host.querySelector('canvas');if(!canvas){canvas=document.createElement('canvas');canvas.width=900;canvas.height=440;host.appendChild(canvas);}
   const c=canvas.getContext('2d'),a=full()?.35+(now-started)*.00017:.6,vertices=model.vertices,faces=[];
   c.clearRect(0,0,900,440);
   const project=i=>{const x=vertices[i*11],y=vertices[i*11+1],z=vertices[i*11+2],xx=x*Math.cos(a)-y*Math.sin(a),yy=x*Math.sin(a)+y*Math.cos(a);return[450+xx*240,220+yy*90-z*240,z+yy*.4];};
   for(let i=0;i<model.indices.length;i+=3){const ids=[model.indices[i],model.indices[i+1],model.indices[i+2]],p=ids.map(project);faces.push({p,depth:p.reduce((s,v)=>s+v[2],0),color:[0,1,2].map(j=>Math.round(vertices[ids[0]*11+3+j]*255))});}
   faces.sort((a,b)=>a.depth-b.depth).forEach(f=>{c.beginPath();f.p.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.closePath();c.fillStyle=`rgb(${f.color.join(',')})`;c.fill();});
  }
  if(full())frame=requestAnimationFrame(draw);
 }
 function scene(){
  if(closed||ready||!window.SeamMap?.engine()||!full())return;
  ready=true;const S=window.Seam,M=window.SeamMap,e=M.engine(),m=e.map;
  backup={ws:S.UI.ws,mode:S.UI.mode,orbit:e.fx?.orbitActive?.()||false,panel:window.SeamShell?.panelOpen(),pose:m?{center:[m.getCenter().lng,m.getCenter().lat],zoom:m.getZoom(),pitch:m.getPitch(),bearing:m.getBearing()}:null};
  if(e.kind==='gl'){
   intro.classList.add('has-live-earth');document.documentElement.dataset.nativeBoot='on';
   if(S.UI.ws!=='overview')S.go('overview');
   window.SeamBasemap?.set('satellite');M.flyPose({mode:'globe',orbit:false,center:[69.5,28.5],zoom:1.8,pitch:0,bearing:-8});
  }
 }
 function finish(enter=false){
  if(closed)return;closed=true;skipped=enter;clearTimeout(clock);cancelAnimationFrame(frame);
  const S=window.Seam,M=window.SeamMap;intro.hidden=true;intro.classList.remove('has-live-earth');document.documentElement.dataset.nativeBoot='off';background().forEach(e=>e.inert=false);
  try{sessionStorage.setItem(key,'seen');}catch(_){}
  if(backup&&S&&M){
   const target=manual?backup.ws:S.UI.ws;
   if(target!==S.UI.ws)S.go(target);
   if(manual&&backup.pose)M.flyPose({...backup.pose,mode:backup.mode,orbit:backup.orbit});
   else {M.setMode(backup.mode,false);M.engine()?.fit(M.bounds(),!enter&&full());}
   if(backup.panel&&backup.ws==='overview')window.SeamShell?.openResults();
   S.syncUrl();
  }
  if(!enter&&full()){
   document.body.classList.add('instrument-dock');setTimeout(()=>document.body.classList.remove('instrument-dock'),850);
   if(window.Seam?.result())window.Seam.emit('scan-reveal-request');
  }
  window.dispatchEvent(new CustomEvent('seam-intro-dismissed',{detail:{skipped:enter,native:true,manual}}));
  if(intro.contains(document.activeElement)){const target=enter?document.getElementById('main'):previous;if(target?.getClientRects().length)target.focus({preventScroll:true});}
 }
 function tick(){
  if(closed||document.hidden)return;
  const elapsed=performance.now()-started;scene();
  if(ready&&elapsed>1750&&!scanStarted){scanStarted=true;window.SeamMap?.setOrbit(true);status.textContent=window.Seam?.result()?'Observation record ready':'Loading the selected observations…';}
  if(elapsed>3100&&ready&&!descentStarted&&window.SeamMap?.engine()?.kind==='gl'){descentStarted=true;window.SeamMap.flyPose({mode:'globe',center:[71,30.5],zoom:2.9,pitch:15,bearing:0});}
  if(elapsed>=4400){finish();return;}clock=setTimeout(tick,100);
 }
 function open(explicit=true){
  clearTimeout(clock);cancelAnimationFrame(frame);closed=false;manual=explicit;skipped=false;ready=false;scanStarted=false;descentStarted=false;backup=null;started=performance.now();previous=document.activeElement;
  intro.hidden=false;intro.classList.add('is-native');status.textContent=window.Seam?.result()?'Your workspace is ready':'Loading the observation record…';button.textContent='Open workspace';background().forEach(e=>e.inert=true);button.focus({preventScroll:true});draw(started);
  if(full()){scene();tick();}else if(!manual)clock=setTimeout(()=>finish(),250);
 }
 button.addEventListener('click',()=>finish(true));intro.addEventListener('keydown',e=>{if(e.key==='Escape')finish(true);if(e.key==='Tab'){e.preventDefault();button.focus();}});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);clearTimeout(clock);}else if(!closed){draw(performance.now());tick();}});
 window.SeamIntro={open,dismiss:finish,ready(){if(!closed)status.textContent='Your workspace is ready';},wasSkipped:()=>skipped,usedCinematic:()=>false,isOpen:()=>!closed,native:true};
 document.addEventListener('DOMContentLoaded',()=>{window.Seam?.on('ready',scene);window.Seam?.on('motion',()=>{if(!closed&&!full())finish();});if(query.get('intro')==='1'||(!seen&&query.get('intro')!=='0'))open(false);});
})();
