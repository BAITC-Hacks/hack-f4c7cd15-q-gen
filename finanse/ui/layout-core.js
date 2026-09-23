// Pure, stable layout: no random numbers, physics, or fabricated graph edges.
export function computeLayout(nodes,mode){
 const clusters=[...new Set(nodes.map(n=>n.cluster_id))].sort((a,b)=>a-b), centers=new Map(),placed=[];
 const sizes=new Map(clusters.map(c=>{const members=nodes.filter(n=>n.cluster_id===c);return [c,mode==='cluster'?members.length:Math.max(...[0,1,2,3,4].map(d=>members.filter(n=>n.depth===d).length))];}));
 // Pack cluster footprints without overlap, largest first. Search is finite and runs in the worker.
 for(const c of [...clusters].sort((a,b)=>sizes.get(b)-sizes.get(a)||a-b)){
  const radius=11*Math.sqrt(sizes.get(c))+22;let point;
  for(let i=0;i<100000;i++){const angle=i*2.399963229728653,r=14*Math.sqrt(i),x=r*Math.cos(angle),y=r*Math.sin(angle);if(placed.every(p=>Math.hypot(x-p.x,y-p.y)>radius+p.radius+12)){point=[x,y];break;}}
  if(!point)throw Error('Не удалось расположить кластеры без пересечений');centers.set(c,point);placed.push({x:point[0],y:point[1],radius});
 }
 const groups=new Map();for(const n of [...nodes].sort((a,b)=>a.gid.localeCompare(b.gid))){const key=mode==='cluster'?String(n.cluster_id):`${n.depth}:${n.cluster_id}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(n);}
 const result={};for(const group of groups.values())group.forEach((n,i)=>{const [cx,cy]=centers.get(n.cluster_id),angle=i*2.399963229728653,r=11*Math.sqrt(i),depth=Number(n.depth);result[n.gid]=mode==='cluster'?[cx+r*Math.cos(angle),cy+r*Math.sin(angle),(depth-2)*19]:[cx+r*Math.cos(angle), (2-depth)*230, cy+r*Math.sin(angle)];});return result;
}
