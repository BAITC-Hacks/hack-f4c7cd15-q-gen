import * as T from '../vendor/three.module.js';
import {OrbitControls} from '../vendor/OrbitControls.js';
import {radius,thickness,edgePoints} from './geometry.js';
import {nodeColor} from './legend.js';
export class Scene3D{
 constructor(host,{onSelect,onEdge,onHover,onFailure}){
  this.host=host;this.handlers={onSelect,onEdge,onHover};this.abort=new AbortController();this.scene=new T.Scene();this.scene.background=new T.Color('#f8faf8');
  this.camera=new T.PerspectiveCamera(42,1,.1,20000);const canvas=document.createElement('canvas'),context=canvas.getContext('webgl2',{antialias:true});if(!context)throw Error('WebGL 2 недоступен в браузере');this.renderer=new T.WebGLRenderer({canvas,context,antialias:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.append(this.renderer.domElement);this.canvas=this.renderer.domElement;this.canvas.setAttribute('aria-label','3D-граф. Вращение левой кнопкой, перемещение правой, масштаб колесом. Поиск и кнопки камеры доступны с клавиатуры.');
  this.controls=new OrbitControls(this.camera,this.canvas);this.controls.enableDamping=false;this.controls.autoRotate=false;this.controls.addEventListener('change',()=>this.invalidate());
  this.scene.add(new T.HemisphereLight(0xffffff,0x68766c,2.4));const light=new T.DirectionalLight(0xffffff,3);light.position.set(-300,600,800);this.scene.add(light);
  this.group=new T.Group();this.scene.add(this.group);this.ray=new T.Raycaster();this.pointer=new T.Vector2();this.labels=document.createElement('div');this.labels.className='graph-labels';host.append(this.labels);
  this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(host);
  const options={signal:this.abort.signal};let down;
  this.canvas.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY,moved:false};},options);
  this.canvas.addEventListener('pointermove',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)down.moved=true;if(e.buttons)return;this.pointerEvent(e,false);},options);
  this.canvas.addEventListener('pointerup',e=>{if(down&&!down.moved&&e.button===0)this.pointerEvent(e,true);down=null;},options);
  this.canvas.addEventListener('pointerleave',()=>onHover?.(null),options);
  this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();onFailure?.('WebGL-контекст потерян. Включён 2D-режим.');},options);
  this.resize();
 }
 invalidate(){if(this.disposed||this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=null;if(this.disposed)return;this.renderer.render(this.scene,this.camera);this.canvas.dataset.drawCalls=String(this.renderer.info.render.calls);this.canvas.dataset.frames=String((Number(this.canvas.dataset.frames)||0)+1);this.drawLabels();});}
 resize(){const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.renderer.setSize(w,h);this.invalidate();}
 clear(){while(this.group.children.length){const obj=this.group.children[0];this.group.remove(obj);obj.geometry?.dispose();obj.material?.dispose();obj.dispose?.();}}
 setData(graph,positions,state){this.graph=graph;this.positions=positions;this.state=state;this.clear();this.neighbors=new Set();for(const e of graph.edges)if(e.src===state.gid||e.dst===state.gid){this.neighbors.add(e.src);this.neighbors.add(e.dst);}
  const dummy=new T.Object3D(),color=new T.Color();const mesh=(geometry,material,count)=>{const m=new T.InstancedMesh(geometry,material,Math.max(count,1));m.count=count;this.group.add(m);return m;};
  this.nodes=mesh(new T.SphereGeometry(1,14,10),new T.MeshStandardMaterial({roughness:.45,metalness:.12}),graph.nodes.length);
  graph.nodes.forEach((n,i)=>{dummy.position.fromArray(positions[n.gid]);dummy.rotation.set(0,0,0);dummy.scale.setScalar(radius(n));dummy.updateMatrix();this.nodes.setMatrixAt(i,dummy.matrix);this.nodes.setColorAt(i,color.set(nodeColor(n,state,this.neighbors)));});this.nodes.instanceMatrix.needsUpdate=true;if(this.nodes.instanceColor)this.nodes.instanceColor.needsUpdate=true;
  const seeds=graph.nodes.filter(n=>n.is_seed),boundary=graph.nodes.filter(n=>n.truncated_by_depth);
  for(const [list,geo]of [[seeds,new T.TorusGeometry(1,.065,4,24)],[boundary,new T.TorusGeometry(1,.07,4,4)]]){const m=mesh(geo,new T.MeshBasicMaterial({color:0x65726a}),list.length);list.forEach((n,i)=>{dummy.position.fromArray(positions[n.gid]);dummy.rotation.set(0,0,list===boundary?Math.PI/4:0);dummy.scale.setScalar(radius(n)+2.5);dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);});}
  this.nodeById=new Map(graph.nodes.map(n=>[n.gid,n]));const paths=graph.edges.map(e=>edgePoints(e,positions)),count=paths.reduce((s,p)=>s+p.length-1,0);this.edgeMesh=mesh(new T.CylinderGeometry(1,1,1,4),new T.MeshBasicMaterial(),count);this.edgeIndex=[];
  this.arrows=mesh(new T.ConeGeometry(1,1,5),new T.MeshBasicMaterial(),graph.edges.length);
  const up=new T.Vector3(0,1,0),a=new T.Vector3(),b=new T.Vector3(),delta=new T.Vector3();let index=0;
  graph.edges.forEach((e,i)=>{const active=e.src===state.gid||e.dst===state.gid,c=active?(e.src===state.gid?'#15803d':'#527e69'):(state.gid?'#e5eae6':'#b5beb7'),width=thickness(e)*(active?1.35:1),points=paths[i];
   for(let j=1;j<points.length;j++){a.fromArray(points[j-1]);b.fromArray(points[j]);delta.subVectors(b,a);dummy.position.copy(a).add(b).multiplyScalar(.5);dummy.quaternion.setFromUnitVectors(up,delta.clone().normalize());dummy.scale.set(width,delta.length(),width);dummy.updateMatrix();this.edgeMesh.setMatrixAt(index,dummy.matrix);this.edgeMesh.setColorAt(index,color.set(c));this.edgeIndex[index++]=i;}
   // Place arrowhead outside the target sphere along the actual curve.
   const end=new T.Vector3().fromArray(positions[e.dst]),targetRadius=radius(this.nodeById.get(e.dst))+6;let j=points.length-2;while(j>0&&new T.Vector3().fromArray(points[j]).distanceTo(end)<targetRadius)j--;
   a.fromArray(points[j]);b.fromArray(points[j+1]);dummy.position.copy(a);dummy.quaternion.setFromUnitVectors(up,delta.subVectors(b,a).normalize());dummy.scale.set(active?3.4:2.5,active?8:6,active?3.4:2.5);dummy.updateMatrix();this.arrows.setMatrixAt(i,dummy.matrix);this.arrows.setColorAt(i,color.set(c));
  });
  this.labelNodes=graph.nodes.filter(n=>n.gid===state.gid||this.neighbors.has(n.gid)).sort((a,b)=>(b.gid===state.gid)-(a.gid===state.gid)||b.priority_score-a.priority_score).slice(0,16);this.labels.replaceChildren();for(const n of this.labelNodes){const label=document.createElement('span');label.textContent=n.gid===state.gid?n.gid:'…'+n.gid.slice(-7);this.labels.append(label);}this.invalidate();
 }
 drawLabels(){if(!this.labelNodes)return;
  if(!this.state.gid){
   const close=this.camera.position.distanceTo(this.controls.target)<500;
   this.labelNodes=close?this.graph.nodes.filter(n=>{const v=new T.Vector3().fromArray(this.positions[n.gid]).project(this.camera);return Math.abs(v.x)<.9&&Math.abs(v.y)<.9&&v.z<1&&v.z> -1;}).sort((a,b)=>b.priority_score-a.priority_score).slice(0,12):[];
   this.labels.replaceChildren();for(const n of this.labelNodes){const label=document.createElement('span');label.textContent='...'+n.gid.slice(-7);this.labels.append(label);}
  }
const occupied=[];this.labelNodes.forEach((n,i)=>{const v=new T.Vector3().fromArray(this.positions[n.gid]).project(this.camera),el=this.labels.children[i],x=(v.x+1)/2*this.host.clientWidth+8,y=(-v.y+1)/2*this.host.clientHeight-20,w=n.gid===this.state.gid?125:65;const rect=[x,y,x+w,y+18];el.hidden=v.z>1||v.z< -1||x<0||x+w>this.host.clientWidth||y<0||y+18>this.host.clientHeight||occupied.some(r=>rect[0]<r[2]+5&&rect[2]>r[0]-5&&rect[1]<r[3]+3&&rect[3]>r[1]-3);if(!el.hidden)occupied.push(rect);el.style.left=`${(v.x+1)/2*100}%`;el.style.top=`${(-v.y+1)/2*100}%`;});}
 pointerEvent(e,select){if(!this.nodes)return;const r=this.canvas.getBoundingClientRect();this.pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);this.ray.setFromCamera(this.pointer,this.camera);const hit=this.ray.intersectObject(this.nodes)[0];if(hit){const n=this.graph.nodes[hit.instanceId];if(select)this.handlers.onSelect(n.gid);else this.handlers.onHover?.(n,e);this.canvas.style.cursor='pointer';return;}this.canvas.style.cursor='grab';this.handlers.onHover?.(null);if(select){const h=this.ray.intersectObjects([this.arrows,this.edgeMesh])[0];if(h)this.handlers.onEdge(this.graph.edges[h.object===this.arrows?h.instanceId:this.edgeIndex[h.instanceId]]);}}
 fit(top=false){if(!this.graph?.nodes.length)return;const box=new T.Box3();for(const n of this.graph.nodes)box.expandByPoint(new T.Vector3().fromArray(this.positions[n.gid]));const center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3()),distance=Math.max(100,size.length()*.72/Math.min(this.camera.aspect,1));this.controls.target.copy(center);this.camera.up.set(0,top?0:1,top?-1:0);this.camera.position.copy(center).add(top?new T.Vector3(0,distance,.001):new T.Vector3(distance*.28,distance*.18,distance));this.controls.update();this.invalidate();}
 focus(gid){const p=this.positions?.[gid];if(!p)return;const target=new T.Vector3().fromArray(p),offset=this.camera.position.clone().sub(this.controls.target).normalize().multiplyScalar(180);this.controls.target.copy(target);this.camera.position.copy(target).add(offset);this.controls.update();this.invalidate();}
 zoom(factor){this.camera.position.sub(this.controls.target).multiplyScalar(factor).add(this.controls.target);this.controls.update();this.invalidate();}
 dispose(){this.disposed=true;cancelAnimationFrame(this.frame);this.abort.abort();this.observer.disconnect();this.controls.dispose();this.clear();this.renderer.dispose();this.renderer.forceContextLoss();this.canvas.remove();this.labels.remove();}
}
