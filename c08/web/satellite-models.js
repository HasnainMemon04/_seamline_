/* Original lightweight spacecraft meshes, Apache-2.0 under this project's LICENSE.
   Schematic geometry, not engineering models or real-time tracking. No external assets. */
(() => {
  'use strict';
  const gold=[.76,.57,.27,1],metal=[.76,.81,.85,1],blue=[.10,.28,.45,1],cell=[.20,.47,.66,1],dark=[.07,.11,.15,1];
  function create(kind) {
    const vertices=[],indices=[];
    function face(points,color) {
      const [a,b,c]=points,u=b.map((v,i)=>v-a[i]),v=c.map((n,i)=>n-a[i]);
      const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],len=Math.hypot(...n)||1,start=vertices.length/11;
      points.forEach(p=>vertices.push(...p,...color,...n.map(x=>x/len),1));
      for(let i=1;i<points.length-1;i++)indices.push(start,start+i,start+i+1);
    }
    function box(x,y,z,w,h,d,color) {
      const p=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(p=>[x+p[0]*w/2,y+p[1]*h/2,z+p[2]*d/2]);
      [[0,3,2,1],[4,5,6,7],[0,1,5,4],[2,3,7,6],[1,2,6,5],[3,0,4,7]].forEach(ids=>face(ids.map(i=>p[i]),color));
    }
    function panel(y,h) {
      box(0,y,0,.45,h,.025,blue);
      for(let i=0;i<5;i++)box(0,y-h/2+(i+1)*h/6,.017,.43,.009,.007,cell);
      box(0,y,.019,.009,h,.006,metal);
    }
    const eos=kind==='Terra'||kind==='Aqua';
    box(0,0,.03,eos?.37:.32,.25,.26,gold);box(0,-.018,-.15,.22,.19,.10,metal);box(.02,-.08,-.21,.12,.08,.035,dark);
    box(0,.35,0,.028,.65,.035,metal);panel(.60,.65);
    if(!eos){box(0,-.35,0,.028,.65,.035,metal);panel(-.60,.65);}
    if(kind==='Aqua')box(.24,0,.02,.17,.13,.16,metal);
    box(-.12,0,.25,.018,.018,.22,metal);
    for(let i=0;i<8;i++){
      const a=i*Math.PI/4,b=(i+1)*Math.PI/4;
      face([[-.12,0,.30],[-.12+Math.cos(a)*.09,Math.sin(a)*.09,.35],[-.12+Math.cos(b)*.09,Math.sin(b)*.09,.35]],metal);
    }
    return {vertices:new Float32Array(vertices),indices:new Uint32Array(indices),schematic:true};
  }
  const models=new Map(['Terra','Aqua','SNPP','NOAA20','NOAA21'].map(k=>[k,create(k)]));
  window.SeamSatelliteModels={models,load:()=>{},credit:'Original Seamline schematic spacecraft · Apache-2.0',schematic:true};
  window.dispatchEvent(new Event('satellite-models-ready'));
})();
