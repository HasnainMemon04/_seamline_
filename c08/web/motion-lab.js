/* Native instrument interactions. Animation decorates real data; it never changes observations or exports. */
(() => {
 'use strict';
 const S=window.Seam,$=id=>document.getElementById(id),root=document.documentElement;
 if(!S)return;
 const full=()=>S.motionMode()==='full',esc=S.esc,fmt=S.fmt;
 let installed=false,scanFrame=0,playFrame=0,scanStart=0,scanTimeout=0,observedMap=null,mini=null,diagnosticData=null,oldPaths=[],modelChoice=null;
 const lastValues=new Map();
 const ease=t=>1-Math.pow(1-t,3);
 function runScan(){
  const e=window.SeamMap?.engine(),P=window.SeamMap?.points();
  if(!e||!P?.lon.length)return;
  if(e.kind!=='gl'||!full()){S.toast('Recorded detections are shown. Animated scan needs WebGL and full motion.');return;}
  cancelAnimationFrame(scanFrame);clearTimeout(scanTimeout);window.SeamMap.setOrbit(true);e.fx?.setSwaths(true);scanStart=performance.now();
  $('motion-scan-note').hidden=false;
  const tick=now=>{
   if(document.hidden||!['overview','explore'].includes(S.UI.ws)||!full()){stopScan();return;}
   const t=Math.min(1,(now-scanStart)/2400);e.fx?.setScan(t,true);
   if(t<1)scanFrame=requestAnimationFrame(tick);else scanTimeout=setTimeout(stopScan,450);
  };scanFrame=requestAnimationFrame(tick);
 }
 function stopScan(){clearTimeout(scanTimeout);cancelAnimationFrame(scanFrame);scanFrame=0;window.SeamMap?.engine()?.fx?.setScan(0,false);if($('motion-scan-note'))$('motion-scan-note').hidden=true;}
 let lastPlayDay=-1,playChanged=0;
 function playheadTick(now){
  const ph=$('motion-playhead');if(!ph)return;
  if(document.hidden||!full()||$('play-btn').getAttribute('aria-pressed')!=='true'){ph.hidden=true;return;}
  if(lastPlayDay!==S.UI.mapDay){lastPlayDay=S.UI.mapDay;playChanged=now;}
  const n=window.SeamMap.points()?.days_in_month||30,t=Math.min(1,(now-playChanged)/750);
  ph.hidden=false;ph.style.left=`${Math.min(100,((lastPlayDay+t+.5)/(n+1))*100)}%`;playFrame=requestAnimationFrame(playheadTick);
 }
 function quick(open){const p=$('motion-quick-panel');if(!p)return;p.hidden=!open;$('shell-selection').setAttribute('aria-expanded',String(open));if(open)p.querySelector('select').focus();else $('shell-selection').focus({preventScroll:true});}
 function syncQuick(){
  if(!installed||!S.meta())return;const r=S.result();
  if(!$('motion-month').options.length){
   $('motion-region').innerHTML=S.meta().regions.map(v=>`<option>${esc(v)}</option>`).join('');
   const [lo,hi]=S.meta().years,a=[];for(let y=hi;y>=lo;y--)for(let m=12;m>=1;m--)a.push(`<option value="${y}-${String(m).padStart(2,'0')}">${S.MONTH_FULL[m-1]} ${y}</option>`);$('motion-month').innerHTML=a.join('');
  }
  if(r){$('motion-region').value=r.request.region||r.region;$('motion-model').value=r.model;}
  const [y,m]=S.dayMonth();$('motion-month').value=`${y}-${String(m).padStart(2,'0')}`;
 }
 function install(){
  if(installed||!$('map-host'))return;installed=true;
  const dock=document.createElement('details');dock.id='motion-layer-dock';dock.className='motion-layer-dock';dock.innerHTML=`<summary>Orbit &amp; detection layers</summary><label><input type="checkbox" id="motion-footprints">Pixel footprints</label><label><input type="checkbox" id="motion-swaths" checked>Sensor swaths</label><label><input type="checkbox" id="motion-tracks" checked>Orbit tracks</label><label><input type="checkbox" id="motion-frp">3D FRP gradient</label><button type="button" class="btn" id="motion-scan">Replay scan reveal</button><p class="note">Footprints and FRP are alternative views. Orbits and swaths are illustrative.</p>`;
  $('map-host').appendChild(dock);
  const note=document.createElement('p');note.id='motion-scan-note';note.className='motion-scan-note';note.hidden=true;note.textContent='Illustrative scan reveal · sampled glow on recorded pixels · not ignition timing';$('map-host').appendChild(note);
  const q=document.createElement('div');q.id='motion-quick-panel';q.className='motion-quick-panel';q.setAttribute('role','dialog');q.setAttribute('aria-label','Quick selection');q.hidden=true;
  q.innerHTML=`<label>Area<select id="motion-region"></select></label><label>Map &amp; daily month<select id="motion-month"></select></label><label>Harmonisation model<select id="motion-model"><option value="M1">M1 · single ratio</option><option value="M2">M2 · monthly ratios</option></select></label><button type="button" class="btn" id="motion-full-selection">Full selection &amp; compare month</button><p class="note">The seasonal ratio changes with the analysis/model, not simply with the map month.</p>`;
  $('shell-map-ui').appendChild(q);$('shell-selection').setAttribute('aria-controls',q.id);$('shell-selection').setAttribute('aria-haspopup','dialog');
  $('shell-selection').addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();quick(q.hidden);},{capture:true});
  q.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();quick(false);}else S.trapTab(q,e);});
  $('motion-region').addEventListener('change',e=>S.selectArea(e.target.value));
  $('motion-month').addEventListener('change',e=>{const [y,m]=e.target.value.split('-').map(Number);S.setDayMonth(y,m);});
  $('motion-model').addEventListener('change',e=>S.selectModel(e.target.value));
  $('motion-full-selection').addEventListener('click',()=>{quick(false);S.openSheet(null,$('shell-selection'));});
  document.addEventListener('click',e=>{if(!q.hidden&&!q.contains(e.target)&&!$('shell-selection').contains(e.target)){q.hidden=true;$('shell-selection').setAttribute('aria-expanded','false');}});
  $('motion-footprints').addEventListener('change',e=>{if(e.target.checked)$('motion-frp').checked=false;window.SeamMap.setViewMode(e.target.checked?'footprints':'points');});
  $('motion-frp').addEventListener('change',e=>{if(e.target.checked)$('motion-footprints').checked=false;window.SeamMap.setViewMode(e.target.checked?'towers':'points');});
  for(const [id,method] of [['motion-swaths','setSwaths'],['motion-tracks','setTracks']])$(id).addEventListener('change',e=>{window.SeamMap.setOrbit($('motion-swaths').checked||$('motion-tracks').checked);window.SeamMap.engine()?.fx?.[method](e.target.checked);});
  $('motion-scan').addEventListener('click',runScan);
  const lat=document.createElement('span');lat.id='motion-lat-label';lat.className='motion-lat-label';$('map-host').appendChild(lat);
  const head=document.createElement('button');head.type='button';head.id='motion-diagnostic-open';head.className='btn motion-diag-trigger';head.textContent='Model diagnostics ↗';head.addEventListener('click',()=>diagnostics(head));$('simple-next-placeholder')?.appendChild(head);
  document.querySelector('#simple-comparison .simple-next').appendChild(head);
  const advanced=head.cloneNode(true);advanced.id='motion-diagnostic-advanced';advanced.addEventListener('click',()=>diagnostics(advanced));$('insight-card').appendChild(advanced);
  document.querySelectorAll('[data-wf="harm"]').forEach(b=>b.addEventListener('click',()=>diagnostics(b)));
  const playhead=document.createElement('span');playhead.id='motion-playhead';playhead.className='motion-playhead';playhead.hidden=true;document.querySelector('.scrub-track').appendChild(playhead);
  $('play-btn').addEventListener('click',()=>queueMicrotask(()=>{cancelAnimationFrame(playFrame);lastPlayDay=-1;playheadTick(performance.now());}));
  syncQuick();refresh();
 }
 function tweenMetrics(){
  for(const [i,node] of [...document.querySelectorAll('#simple-values strong')].entries()){
   const text=node.textContent,key='metric'+i,value=/^[\d,.]+×$/.test(text)?Number(text.replace(/[×,]/g,'')):null,previous=lastValues.get(key);lastValues.set(key,value);
   if(!full()||previous==null||value==null||previous===value)continue;
   node.style.setProperty('--motion-metric-ink',getComputedStyle(node).color);node.classList.add('is-metric-tweening');const start=performance.now();
   const tick=now=>{if(!node.isConnected)return;const t=Math.min(1,(now-start)/360);node.dataset.displayValue=fmt(previous+(value-previous)*ease(t),2)+'×';if(t<1&&!document.hidden)requestAnimationFrame(tick);else{node.classList.remove('is-metric-tweening');delete node.dataset.displayValue;}};requestAnimationFrame(tick);
  }
  const paths=[...document.querySelectorAll('#simple-trend path')],next=paths.map(p=>p.getAttribute('d'));
  paths.forEach((p,i)=>{const from=oldPaths[i],to=next[i];if(!full()||!from||from===to)return;const pattern=/[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi,a=from.match(pattern)?.map(Number),b=to.match(pattern)?.map(Number);if(!a||!b||a.length!==b.length||from.replace(pattern,'#')!==to.replace(pattern,'#')){p.animate([{opacity:0},{opacity:1}],{duration:220});return;}const start=performance.now();const tick=now=>{if(!p.isConnected)return;const t=Math.min(1,(now-start)/320);let j=0;p.setAttribute('d',to.replace(pattern,()=>String(a[j]+(b[j]-a[j++])*ease(t))));if(t<1&&!document.hidden)requestAnimationFrame(tick);else p.setAttribute('d',to);};requestAnimationFrame(tick);});oldPaths=next;
 }
 function models(){
  const e=S.meta()?.evidence,r=S.result();if(!e||!r)return;
  let host=$('motion-model-host');if(!host){host=document.createElement('div');host.id='motion-model-host';$('simple-pane-evidence').appendChild(host);}
  const data=e.sensitivity_octnov||{};
  host.innerHTML=`<table class="motion-model-table"><caption>Saved Punjab · October–November sensitivity (E03)</caption><thead><tr><th>Model</th><th>Ratio</th><th>Use</th></tr></thead><tbody>${Object.entries(data).map(([k,v])=>`<tr data-motion-row="${k}" class="${k===(modelChoice||r.model)?'is-selected':''}"><th><button type="button" data-motion-model="${k}">${k}</button></th><td>${fmt(v.ratio,2)}×</td><td>${['M1','M2'].includes(k)?'Live model':'Saved sensitivity'}</td></tr>`).join('')}</tbody></table><p id="motion-model-detail" class="motion-model-detail">M3/M4 are saved Punjab sensitivity cases; selecting them highlights their benchmark without changing live calculations.</p>`;
 }
 function refresh(){if(!installed)return;syncQuick();tweenMetrics();models();const M=window.SeamMap,e=M?.engine(),m=e?.map;const lat=$('motion-lat-label');if(m&&lat){const v=m.getCenter().lat;lat.textContent=`Centre ${Math.abs(v).toFixed(1)}°${v<0?'S':'N'}`;lat.hidden=!e.fx?.orbitActive();}const dock=$('motion-layer-dock');if(dock){dock.hidden=S.UI.ws!=='overview'&&S.UI.ws!=='explore';if(root.dataset.experience==='advanced')dock.open=true;}if(m&&observedMap!==m){observedMap=m;m.on('moveend',refresh);}placeDock();syncModelRows();}

 function placeDock(){const host=$('map-host'),status=$('shell-map-status');if(!host||!status)return;const a=host.getBoundingClientRect(),b=status.getBoundingClientRect();if(b.height)host.style.setProperty('--motion-dock-bottom',Math.ceil(a.bottom-b.top+16)+'px');}
 function syncModelRows(){const k=modelChoice||S.result()?.model;document.querySelectorAll('#insight-metrics tr').forEach(row=>{const cell=row.querySelector('th,td'),name=cell?.textContent.trim().match(/^M[1-4]\b/)?.[0];row.classList.toggle('is-motion-selected',name===k);if(name&&!cell.querySelector('button')){const button=document.createElement('button');button.type='button';button.dataset.motionModel=name;button.textContent=cell.textContent;cell.replaceChildren(button);}});}
 new ResizeObserver(placeDock).observe($('shell-map-status'));
 document.addEventListener('click',e=>{const b=e.target.closest('[data-motion-model]');if(!b)return;modelChoice=b.dataset.motionModel;syncModelRows();document.querySelectorAll('[data-motion-row]').forEach(r=>r.classList.toggle('is-selected',r.dataset.motionRow===modelChoice));if(['M1','M2'].includes(modelChoice))S.selectModel(modelChoice);else $('motion-model-detail').textContent=`${modelChoice}: ${fmt(S.meta().evidence.sensitivity_octnov[modelChoice].ratio,2)}× in saved Punjab October–November E03. The live ${S.result().model} result is unchanged.`;});
 const svg=(host,label)=>S.el('svg',{viewBox:'0 0 360 175',role:'img','aria-label':label},host);
 const text=(g,x,y,t,anchor='start')=>{const n=S.el('text',{x,y,'text-anchor':anchor,style:`font:10px ${S.css('--font')};fill:${S.css('--muted')}`},g);n.textContent=t;};
 function scatter(host,r){const g=svg(host,'Aqua and S-NPP monthly observed fire pixels, 2012 to 2017');const pts=r.months.filter(m=>m.month>='2012-02'&&m.month<='2017-12'&&!m.aqua_flag&&!m.H_flag&&[m.Aqua_D,m.Aqua_N,m.SNPP_D,m.SNPP_N].every(v=>v!=null)&&!/partial|outside|unavailable/.test(m.Aqua_status+' '+m.SNPP_status)).map(m=>[m.Aqua_D+m.Aqua_N,m.SNPP_D+m.SNPP_N]);if(!pts.length){text(g,20,80,'No eligible overlap months');return;}const max=Math.max(...pts.flat())+1,log=v=>Math.log10(v+1)/Math.log10(max),x=v=>42+log(v)*300,y=v=>140-log(v)*120;S.el('path',{d:'M42 15V140H344',fill:'none',stroke:S.css('--axis')},g);pts.forEach(p=>S.el('circle',{cx:x(p[0]),cy:y(p[1]),r:2.4,fill:S.css('--accent'),'fill-opacity':.7},g));text(g,42,160,'Aqua (log10 + 1)');text(g,340,20,'S-NPP', 'end');text(g,340,160,pts.length+' eligible months','end');}
 function histogram(host,d){const g=svg(host,'Saved Punjab yearly M2 WAPE distribution, 2018 to 2025');const values=d.years.map(y=>y.M2*100).filter(Number.isFinite),max=Math.max(...values,1),bins=Array(5).fill(0);values.forEach(v=>bins[Math.min(4,Math.floor(v/(max+1)*5))]++);const h=Math.max(...bins,1);bins.forEach((n,i)=>{const x=36+i*62,y=140-n/h*105;S.el('rect',{x,y,width:48,height:140-y,fill:S.css('--accent'),'fill-opacity':.7},g);text(g,x+24,y-6,String(n),'middle');text(g,x+24,157,Math.round(i*(max+1)/5)+'%','middle');});text(g,35,15,'Years');text(g,342,172,'WAPE bin (%)','end');}
 function passes(host,P){const g=svg(host,'Current map-month observed day and night detections by sensor');if(!P){text(g,20,80,'Map observations not loaded');return;}const values=S.SATS.map(k=>({k,...P.counts[k],outside:/outside|unavailable/.test(P.record?.[k]?.status||'')})),max=Math.max(1,...values.flatMap(v=>v.outside?[]:[v.D||0,v.N||0]));values.forEach((v,i)=>{const x=25+i*66;if(v.outside)text(g,x+15,115,'—','middle');else for(const [j,k] of ['D','N'].entries()){const h=Math.sqrt((v[k]||0)/max)*110;S.el('rect',{x:x+j*18,y:135-h,width:15,height:h,fill:j?S.css('--muted'):S.css('--accent')},g);}text(g,x+15,153,S.SAT_INFO[v.k].short,'middle');});text(g,25,17,'Day / night · √ scale');}
 async function diagnostics(opener){
  const r=S.result();if(!r)return;
  S.openDialog(`Model ${r.model} · diagnostic analysis`,`<p class="note">${esc(r.region)} · monthly overlap checks and current-map observations. Reference is another satellite, not ground truth.</p><div class="motion-diag-grid"><figure><figcaption>MODIS / VIIRS observed overlap</figcaption><div id="motion-scatter"></div><p class="note">Aqua versus S-NPP, 2012–2017. Observations, not held-out predictions.</p></figure><figure><figcaption>Saved M2 WAPE histogram</figcaption><div id="motion-hist"></div><p class="note">Punjab annual drift checks, 2018–2025 · E02. This benchmark is separate from the current area's CV.</p></figure><figure><figcaption>Selected region · ${esc(window.SeamMap.points()?.month||'loading')}</figcaption><div id="motion-mini-map" class="motion-diag-map"></div><p class="note">Same filtered observations as the main map.</p></figure><figure><figcaption>Day / night sensor sampling</figcaption><div id="motion-passes"></div><p class="note">Observed pixels per satellite in the map month. No record is a gap.</p></figure></div>`,opener,()=>{mini?.destroy();mini=null;$('dialog').classList.remove('motion-diagnostic');});
  $('dialog').classList.add('motion-diagnostic');scatter($('motion-scatter'),r);passes($('motion-passes'),window.SeamMap.points());
  const M=window.SeamMap,P=M.points();mini=window.SeamMap2D.create($('motion-mini-map'),{colors:M.colors(),geo:S.geo(),areas:S.areas().areas,focusable:false,labels:false});mini.setSelection({region:r.region,bbox:r.request.bbox||null});mini.setPoints(P);mini.setFilter({sats:S.UI.sats.map(k=>S.SATS.indexOf(k)),dn:S.UI.dn,day:S.UI.mapDay});mini.fit(M.bounds());
  try{if(!diagnosticData)diagnosticData=await(await fetch('/static/assets/motion-diagnostics.json')).json();if($('motion-hist'))histogram($('motion-hist'),diagnosticData);}catch(_){if($('motion-hist'))$('motion-hist').textContent='Saved diagnostic unavailable.';}
 }
 async function measure(ms=2500){const map=window.SeamMap?.engine()?.map,intervals=[];let last=performance.now(),renders=0,raf=0;const count=()=>renders++;map?.on('render',count);return new Promise(resolve=>{const start=last,tick=now=>{intervals.push(now-last);last=now;if(now-start<ms)raf=requestAnimationFrame(tick);else{map?.off('render',count);const sorted=intervals.slice(1).sort((a,b)=>a-b),median=sorted[Math.floor(sorted.length/2)]||0;resolve({rafFPS:median?1000/median:0,mapFPS:renders*1000/(now-start),durationMs:now-start,frames:intervals.length});}};raf=requestAnimationFrame(tick);});}
 S.on('ready',install);S.on('selection',()=>{modelChoice=null;refresh();});for(const evt of ['story','theme','daymonth','points-loaded','map-mode','ws'])S.on(evt,refresh);
 S.on('scan-reveal-request',()=>{if(!installed)install();runScan();});S.on('motion',()=>{if(!full())stopScan();});S.on('ws',()=>{if(!['overview','explore'].includes(S.UI.ws))stopScan();});document.addEventListener('visibilitychange',()=>{if(document.hidden){stopScan();cancelAnimationFrame(playFrame);}});
 window.SeamMotion={runScan,stopScan,diagnostics,measure,refresh,scanActive:()=>!!scanFrame};if(S.meta()&&$('map-host'))install();
})();
