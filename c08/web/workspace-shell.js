/* Progressive workspace shell. One selection, one map, unchanged analysis/export contracts. */
(() => {
  'use strict';
  const S = window.Seam, $ = id => document.getElementById(id), root = document.documentElement;
  if (!S) return;
  let panelOpen = false, menuOpener = null, entrancePlayed = false, returnFocus = null;
  const mapWorkspace = () => ['overview', 'explore'].includes(S.UI.ws);
  const format = n => n == null || !Number.isFinite(n) ? '—' : S.fmt(n);
  const mode = () => root.dataset.experience === 'advanced' ? 'advanced' : 'simple';
  const resize = () => { S.emit('resize'); requestAnimationFrame(() => S.emit('resize')); };
  const isVisible = e => e && !e.hidden && e.getClientRects().length > 0;
  let mapShare=60,resizeFrame=0;
  try{const saved=Number(localStorage.getItem('seamline-map-share'));if(saved>=35&&saved<=80)mapShare=saved;}catch(_){}
  function setSplit(value,persist=false){
    const width=$('main').clientWidth,min=width>760?Math.max(35,280/width*100):35,max=width>760?Math.min(80,100-280/width*100):80;
    mapShare=width>760?Math.max(min,Math.min(max,value)):value;
    root.style.setProperty('--map-share',mapShare+'%');
    root.dataset.mapCompact=String(mapShare<52);
    const handle=$('shell-splitter');
    handle.setAttribute('aria-valuenow',String(Math.round(mapShare)));
    handle.setAttribute('aria-valuetext',`${Math.round(mapShare)}% map, ${Math.round(100-mapShare)}% results`);
    handle.setAttribute('aria-valuemin',String(Math.ceil(min)));handle.setAttribute('aria-valuemax',String(Math.floor(max)));
    if(persist)try{localStorage.setItem('seamline-map-share',String(mapShare));}catch(_){}
    if(!resizeFrame)resizeFrame=requestAnimationFrame(()=>{resizeFrame=0;resize();});
  }

  // Keep the original navigation, research context and credits in a single accessible drawer.
  $('shell-context-home').appendChild($('context'));
  $('shell-footer-home').appendChild(document.querySelector('footer.foot'));
  // Analysis failures must remain visible in Calendar and Evidence as well as the map.
  $('main').appendChild($('shell-error'));

  function navigation(open) {
    const drawer = $('navigation-drawer');
    if (open) {
      menuOpener = document.activeElement;
      $('shell-layers').hidden = true;
      $('shell-layers-button').setAttribute('aria-expanded', 'false');
    }
    drawer.hidden = !open;
    $('navigation-shade').hidden = !open;
    $('navigation-open').setAttribute('aria-expanded', String(open));
    $('main').inert = open;
    $('top').inert = open;
    if (open) $('navigation-close').focus();
    else if (menuOpener && isVisible(menuOpener)) menuOpener.focus();
  }

  function setPanel(open, focus = false) {
    panelOpen = !!open && mapWorkspace();
    root.dataset.results = panelOpen ? 'open' : 'closed';
    $('shell-results').hidden = !panelOpen || S.UI.ws !== 'overview';
    $('ex-side').hidden = !panelOpen || S.UI.ws !== 'explore';
    $('ex-side').classList.remove('is-collapsed');
    $('shell-brief').hidden = panelOpen || S.UI.ws !== 'overview';
    const toggle = $('shell-results-toggle');
    toggle.setAttribute('aria-expanded', String(panelOpen));
    toggle.setAttribute('aria-controls', S.UI.ws === 'explore' ? 'ex-side' : 'shell-results');
    $('shell-results-label').textContent = S.UI.ws === 'explore' ? 'Filters' : 'Results';
    if (focus && panelOpen) {
      const target = S.UI.ws === 'explore' ? $('ex-side') : $('shell-results');
      target.querySelector('[data-close-results]').focus({preventScroll:true});
    }
    resize();
  }

  function setExperience(value, sync = true) {
    root.dataset.experience = value === 'advanced' ? 'advanced' : 'simple';
    document.querySelectorAll('[data-experience]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.experience === mode())));
    try { localStorage.setItem('seamline-experience', mode()); } catch (_) { /* Choice still lasts for this page. */ }
    // A mode switch never changes the request, map filters, camera, or scientific result.
    if (sync && S.result()) S.syncUrl();
    resize();
  }

  function openResults() {
    returnFocus = document.activeElement;
    if (S.UI.ws !== 'overview') S.go('overview', {story:'record'});
    setPanel(true, true);
  }

  function closeResults() {
    setPanel(false);
    (isVisible(returnFocus) ? returnFocus : $('shell-results-toggle')).focus({preventScroll:true});
  }

  function syncObservation() {
    const r = S.result(), points = window.SeamMap?.points(), eng = window.SeamMap?.engine();
    if (!r) return;
    const [year, month] = S.dayMonth();
    $('shell-area').textContent = r.region;
    $('shell-month').textContent = `${S.MONTH_FULL[month - 1]} ${year} · change selection`;
    $('shell-results-scope').textContent = `${r.region} · ${r.years[0]}–${r.years[1]} · ${r.model} · S-NPP-equivalent detections`;
    const satNames = S.UI.sats.map(k => S.SAT_INFO[k].short).join(' + ') || 'No satellite selected';
    const vm = eng?.viewMeta?.();
    const outside = points && S.UI.sats.some(k => ['outside_record','unavailable'].includes(points.record?.[k]?.status));
    const recordFlags = points ? [...new Set(S.UI.sats.flatMap(k => {
      const rec = points.record?.[k];
      return rec ? [rec.status,rec.stream,rec.type_policy,rec.support?.stream,rec.support?.type_screen,...(rec.support?.flags||[])].filter(v => v && /partial|nrt|untyped|outside|unavailable/.test(v)) : [];
    }))] : [];
    const qualifications=[];
    if(recordFlags.some(v=>/partial/.test(v)))qualifications.push('Partial month');
    if(recordFlags.some(v=>/untyped/.test(v)))qualifications.push('NRT, untyped');
    else if(recordFlags.some(v=>/nrt/.test(v)))qualifications.push('NRT');
    if(qualifications.length)qualifications.push('exposure unknown');
    const actualCount = points ? points.lon.reduce((n, _, i) => n + (S.UI.sats.includes(S.SATS[points.p[i]]) && (S.UI.dn === 'DN' || (S.UI.dn === 'N') === (points.dn[i] === 1)) && (!S.UI.mapDay || points.day[i] === S.UI.mapDay) ? 1 : 0), 0) : null;
    const counts = points ? `${format(actualCount)} fire pixels` : 'Loading detections…';
    const sampled = vm?.limited && !$('map-render-pill')?.hidden ? ` · rendered ${format(vm.shown)} of ${format(vm.total)}` : '';
    const pass = S.UI.dn === 'DN' ? 'day + night' : S.UI.dn === 'D' ? 'day passes' : 'night passes';
    $('shell-observation-status').textContent = outside ? `${satNames} · no usable record for this selection` : `${satNames} · ${counts} · ${pass}${sampled}${qualifications.length ? ' · '+qualifications.join(' · ') : ''}`;
    const support = r.calibration.supported ? `Method & support · ${r.warnings.length} notes` : 'Unsupported before 2012 · read notes';
    $('shell-support').textContent = support;
    $('shell-support').classList.toggle('is-warning', !r.calibration.supported);
    $('shell-orbit-note').hidden = $('orbit-btn')?.getAttribute('aria-pressed') !== 'true';
    $('shell-density-key').hidden = !document.querySelector('[data-vmode="density"][aria-pressed="true"]');
    document.querySelectorAll('[data-shell-view]').forEach(b => b.setAttribute('aria-pressed', String(S.UI.mode === b.dataset.shellView)));
  }

  function syncComparison() {
    const r=S.result();if(!r)return;
    const v=r.change?.[S.UI.season],f=(x,d=2)=>x==null?'—':S.fmt(x,d),esc=S.esc;
    $('simple-period').textContent=`${r.region} · ${S.UI.season==='AprMay'?'April–May':'October–November'} · average 2012–2021 ÷ average 2003–2011`;
    if(!v){$('simple-values').innerHTML='<p class="warnbox">This comparison needs both the 2003–2011 and 2012–2021 periods. Use Advanced selection to include those years.</p>';}
    else {
      const estimate=!v.defined?'—':!v.point_in_interval?`${f(v.H_interval[0])}–${f(v.H_interval[1])}×`:`${f(v.H)}×`;
      const interval=v.defined&&v.H_interval?`Rough range ${f(v.H_interval[0])}–${f(v.H_interval[1])}×`:(v.reason||'Not supported for this selection');
      $('simple-values').innerHTML=`<div class="simple-number raw"><span>Raw records joined</span><strong>${f(v.naive)}×</strong><small>Different sensors, uncalibrated</small></div><div class="simple-number harmonised"><span>On a common scale</span><strong>${estimate}</strong><small>${esc(interval)}</small></div>`;
    }
    $('simple-trend').replaceChildren();
    const chart=$('insight-mini').querySelector('svg');
    if(chart){const copy=chart.cloneNode(true);copy.querySelectorAll('path').forEach(p=>{p.style.transition='none';p.style.strokeDashoffset='0';p.style.strokeDasharray='';});$('simple-trend').appendChild(copy);}
    const c=r.calibration,e=S.meta()?.evidence;
    $('simple-uncertainty').textContent=`${c.supported?'This area passed the calibration support check.':'This area has no supported harmonisation before 2012.'} The range is rough; ${e?.interval_coverage!=null?f(e.interval_coverage*100,0)+'% of held-out test months fell inside the nominal 80% ranges.':'read the saved evaluation before relying on it.'} S-NPP is a satellite reference, not independent ground truth.`;
    $('simple-evidence').innerHTML=`<dl><div><dt>Reference</dt><dd>S-NPP-equivalent seasonal detections</dd></div><div><dt>Selected model</dt><dd>${esc(r.model)} · ${c.supported?'area-specific calibration':'unsupported before 2012'}</dd></div><div><dt>Calibration</dt><dd>Overlap months, February 2012–December 2017</dd></div><div><dt>Data source</dt><dd>NASA FIRMS · cached observations</dd></div><div><dt>Selection notes</dt><dd>${r.warnings.length} qualifications to review</dd></div></dl><p class="simple-qualification">Detections are fire pixels on satellite passes. They are not individual fires, burned area or emissions. No independent ground-truth validation is claimed.</p>`;
  }

  function syncWorkspace(ws) {
    root.dataset.workspace = ws;
    $('shell-map-ui').hidden = !mapWorkspace();
    if (!$('navigation-drawer').hidden) navigation(false);
    $('shell-layers').hidden = true;
    $('shell-layers-button').setAttribute('aria-expanded', 'false');
    // Filter navigation opens its tools. Results stay optional on the overview.
    setPanel(ws === 'explore' ? true : ws === 'overview' ? panelOpen : false);
    syncObservation();
  }

  $('navigation-open').addEventListener('click', () => navigation(true));
  $('navigation-close').addEventListener('click', () => navigation(false));
  $('navigation-shade').addEventListener('click', () => navigation(false));
  $('navigation-drawer').addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); navigation(false); }
    if (e.key === 'Tab') S.trapTab($('navigation-drawer'), e);
  });
  document.querySelectorAll('[data-experience]').forEach(b => b.addEventListener('click', () => setExperience(b.dataset.experience)));
  $('shell-selection').addEventListener('click', () => {
    // The original shared form remains the sole owner of selection state.
    S.openSheet(null, $('shell-selection'));
  });
  $('shell-support').addEventListener('click', () => { if (S.result()) S.summaryDialog($('shell-support')); });
  $('shell-results-toggle').addEventListener('click', () => panelOpen ? closeResults() : (returnFocus = $('shell-results-toggle'), setPanel(true, true)));
  $('shell-investigate').addEventListener('click', openResults);
  document.querySelectorAll('[data-close-results]').forEach(b => b.addEventListener('click', closeResults));
  $('shell-layers-button').addEventListener('click', () => {
    const open = $('shell-layers').hidden;
    $('shell-layers').hidden = !open;
    $('shell-layers-button').setAttribute('aria-expanded', String(open));
    if (open) $('shell-layers').querySelector('button').focus();
  });
  document.querySelectorAll('[data-shell-view]').forEach(b => b.addEventListener('click', () => {
    window.SeamMap?.setMode(b.dataset.shellView, true);
    S.syncUrl();
    syncObservation();
  }));
  document.querySelectorAll('[data-basemap]').forEach(b=>b.addEventListener('click',()=>window.SeamBasemap?.set(b.dataset.basemap)));
  $('shell-imagery-toggle').addEventListener('click',()=>window.SeamBasemap?.set(window.SeamBasemap.mode()==='satellite'?'terrain':'satellite'));
  const divider=$('shell-splitter');let dragging=false;
  divider.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;e.preventDefault();dragging=true;divider.setPointerCapture(e.pointerId);root.classList.add('is-resizing');
  });
  divider.addEventListener('pointermove',e=>{if(dragging){const box=$('main').getBoundingClientRect();setSplit((e.clientX-box.left)/box.width*100);}});
  const finishDrag=()=>{if(!dragging)return;dragging=false;root.classList.remove('is-resizing');setSplit(mapShare,true);};
  divider.addEventListener('pointerup',finishDrag);divider.addEventListener('pointercancel',finishDrag);
  divider.addEventListener('dblclick',()=>setSplit(60,true));
  divider.addEventListener('keydown',e=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();
    setSplit(e.key==='Home'?35:e.key==='End'?80:mapShare+(e.key==='ArrowRight'?2:-2),true);
  });
  document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => {
    const M = window.SeamMap;
    if (!M?.engine()) return;
    const satellite = b.dataset.preset === 'satellite';
    if (satellite && M.engine().kind === 'gl') M.setMode('globe', true);
    M.setViewMode(b.dataset.preset === 'density' ? 'density' : 'points');
    M.setOrbit(satellite);
    if (satellite && M.engine().kind !== 'gl') S.toast('Satellite orbits need WebGL. This 2D map keeps the same observations.');
    document.querySelectorAll('[data-preset]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('shell-layers').hidden = true;
    $('shell-layers-button').setAttribute('aria-expanded', 'false');
    $('shell-layers-button').focus();
    syncObservation();
  }));
  $('shell-advanced-layers').addEventListener('click', () => { setExperience('advanced'); S.go('explore'); setPanel(true, true); });
  $('intro-replay').addEventListener('click', () => { navigation(false); window.SeamIntro?.open(); });
  document.querySelectorAll('[data-simple-step]').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('[data-simple-step]').forEach(x=>{const on=x===b;x.setAttribute('aria-selected',String(on));x.tabIndex=on?0:-1;$('simple-pane-'+x.dataset.simpleStep).hidden=!on;});
  }));
  document.querySelector('.simple-steps').addEventListener('keydown',e=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    const buttons=[...document.querySelectorAll('[data-simple-step]')],i=buttons.indexOf(document.activeElement);
    if(i<0)return;e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
    buttons[next].click();buttons[next].focus();
  });
  $('simple-sensor-animation').addEventListener('click',()=>{closeResults();window.SeamMap?.playTransition();});
  $('simple-method-notes').addEventListener('click',()=>S.summaryDialog($('simple-method-notes')));
  $('simple-download').addEventListener('click',()=>S.exportData('monthly.csv',$('simple-download')));
  $('shell-retry-analysis').addEventListener('click',()=>Array.isArray(S.meta()?.regions)&&Array.isArray(S.meta()?.years)&&S.geo()?S.retryAnalysis():location.reload());

  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !$('navigation-drawer').hidden || !$('controls').hidden || !$('dialog').hidden) return;
    if (!$('shell-layers').hidden) {
      $('shell-layers').hidden = true; $('shell-layers-button').setAttribute('aria-expanded','false'); $('shell-layers-button').focus();
    } else if (panelOpen && mapWorkspace()) closeResults();
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.shell-layers-wrap')) { $('shell-layers').hidden = true; $('shell-layers-button').setAttribute('aria-expanded','false'); }
    // Reuse original utility actions, then return to an unobstructed workspace.
    if (e.target.closest('#copy-link, #print-btn, #tour-btn, #export-btn')) {
      if (!$('navigation-drawer').hidden) navigation(false);
    }
  });

  S.on('ws', syncWorkspace);
  S.on('map-mode',syncObservation);
  S.on('points-loaded',()=>{syncObservation();syncComparison();});
  S.on('print',on=>{
    const footer=document.querySelector('footer.foot');
    if(footer)(on?document.body:$('shell-footer-home')).appendChild(footer);
  });
  S.on('analysis-error', message=>{
    root.dataset.analysis='error';$('shell-error').hidden=false;
    $('shell-error-message').textContent=message+(S.result()?' The map and results still show the previous successful selection.':' Your selection is saved; try the analysis again.');
    $('shell-observation-status').textContent=S.result()?'Previous successful selection · analysis request failed':'Analysis could not be loaded';
  });
  S.on('loading', on=>{
    if(on){root.dataset.analysis='loading';$('shell-error').hidden=true;$('shell-retry-analysis').disabled=true;}
    else{$('shell-retry-analysis').disabled=false;}
  });
  S.on('selection',()=>{root.dataset.analysis='ready';$('shell-error').hidden=true;});
  for (const evt of ['selection','daily','daymonth','filters','story','theme']) S.on(evt, syncObservation);
  for (const evt of ['selection','story','theme','resize']) S.on(evt, syncComparison);
  S.on('ready', () => syncWorkspace(S.UI.ws));
  if(S.result())root.dataset.analysis='ready';
  S.on('selection', () => {
    if (!entrancePlayed) {
      entrancePlayed = true;
      // Brief initial orientation on first visit only. Never replace a shared camera selection.
      if (!window.SeamIntro?.native && !(window.SeamIncomingView?.map ?? new URLSearchParams(location.search).has('map')) && mode() === 'simple' && S.UI.ws === 'overview' && S.motionMode() === 'full' && !window.SeamIntro?.wasSkipped()) {
        const enter=()=>{
          if(window.SeamIntro?.wasSkipped())return;
          const cinematic=window.SeamIntro?.usedCinematic();
          if(cinematic)window.SeamBasemap?.set('satellite');
          // The mobile default stays flat; show the same imagery without imposing a camera flight.
          if(cinematic&&S.UI.mode==='2d'){syncObservation();return;}
          window.SeamMap?.entrance?.({cinematic});
        };
        if(!$('satellite-intro').hidden){
          // Warm the real reference map underneath the film; reveal it when the shot ends.
          if(window.SeamIntro?.usedCinematic())window.SeamBasemap?.set('satellite');
          window.addEventListener('seam-intro-dismissed',enter,{once:true});
        }else enter();
      }
    }
  });
  // Point requests resolve after the monthly analysis. Observe the real legend instead of polling.
  const attachLegend = () => {
    const legend = $('map-legend');
    if (!legend) return;
    new MutationObserver(syncObservation).observe(legend, {childList:true,subtree:true,characterData:true});
  };
  if ($('map-legend')) attachLegend(); else S.on('ready', attachLegend);
  window.addEventListener('popstate', () => {
    const exp = new URLSearchParams(location.search).get('experience');
    setExperience(exp === 'advanced' ? 'advanced' : 'simple', false);
  });
  // Responsive results remain a bottom sheet on phones; the underlying selection is untouched.
  const mobile = matchMedia('(max-width: 760px)');
  const responsive = () => { root.dataset.compact = String(mobile.matches);setSplit(mapShare);resize(); };
  mobile.addEventListener('change', responsive);
  window.addEventListener('resize',()=>setSplit(mapShare));
  setExperience(mode(), false);
  syncWorkspace(S.UI.ws);
  syncComparison();
  responsive();
  window.SeamShell = {setExperience, openResults, closeResults, navigation, syncObservation, mode, setSplit, split:()=>mapShare, panelOpen:()=>panelOpen};
})();
