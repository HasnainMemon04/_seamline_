/* NASA Blue Marble reference imagery. Bundled EPSG:3857 tiles; never used in metrics.
   Provenance, reference date and tile identities are in imagery/MANIFEST.json. */
(() => {
  'use strict';
  let mode='terrain',activeMap=null;
  const S=window.Seam;
  function apply(){
    const engine=window.SeamMap?.engine(),map=engine?.map;
    if(!map)return false;
    if(!map.getLayer('prov-line')){map.once('style.load',apply);return false;}
    if(!map.getSource('nasa-blue-marble-global')){
      map.addSource('nasa-blue-marble-global',{type:'raster',tiles:[location.origin+'/static/imagery/{z}/{x}/{y}.jpeg'],tileSize:256,minzoom:0,maxzoom:2,attribution:'NASA Blue Marble / NASA GIBS (static reference)'});
      map.addSource('nasa-blue-marble-region',{type:'raster',tiles:[location.origin+'/static/imagery/{z}/{x}/{y}.jpeg'],tileSize:256,minzoom:3,maxzoom:6,bounds:[55,15,90,43]});
      const before=map.getLayer('prov-fill')?'prov-fill':map.getStyle().layers.find(l=>l.id==='prov-line')?.id;
      for(const key of ['global','region'])map.addLayer({id:'nasa-imagery-'+key,type:'raster',source:'nasa-blue-marble-'+key,layout:{visibility:'none'},paint:{'raster-opacity':1,'raster-fade-duration':150,'raster-saturation':-.08}},before);
    }
    for(const key of ['global','region'])map.setLayoutProperty('nasa-imagery-'+key,'visibility',mode==='satellite'?'visible':'none');
    // Preserve boundaries and detections while allowing the imagery to show through selection fill.
    if(map.getLayer('prov-fill'))map.setPaintProperty('prov-fill','fill-opacity',mode==='satellite'?.04:(S.UI.mode==='globe'?.38:S.UI.mode==='3d'?.30:.56));
    if(activeMap!==map){activeMap=map;map.on('style.load',apply);}
    return true;
  }
  function set(value){
    const engine=window.SeamMap?.engine();
    if(value==='satellite'&&engine?.kind!=='gl'){
      S.toast('Satellite imagery needs WebGL. The 2D fallback retains the same detections and terrain map.');return false;
    }
    mode=value==='satellite'?'satellite':'terrain';apply();
    document.documentElement.dataset.basemap=mode;
    document.querySelectorAll('[data-basemap]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.basemap===mode)));
    const toggle=document.getElementById('shell-imagery-toggle'),note=document.getElementById('shell-imagery-note');
    if(toggle){toggle.setAttribute('aria-pressed',String(mode==='satellite'));toggle.title=mode==='satellite'?'Return to the terrain basemap':'Show satellite imagery (static NASA Blue Marble)';toggle.setAttribute('aria-label',toggle.title);}
    if(note)note.hidden=mode!=='satellite';
    if(S.result())S.syncUrl();
    return true;
  }
  S.on('theme',()=>{if(mode==='satellite')apply();});
  S.on('points-loaded',()=>{if(mode==='satellite')apply();});
  S.on('ws',()=>{if(mode==='satellite')apply();});
  S.on('map-mode',()=>{if(mode==='satellite')apply();});
  const restore=()=>set(new URLSearchParams(location.search).get('basemap')==='satellite'?'satellite':'terrain');
  S.on('ready',restore);
  window.addEventListener('popstate',restore);
  window.SeamBasemap={set,mode:()=>mode,apply};
  if(window.SeamMap?.engine())restore();
})();
