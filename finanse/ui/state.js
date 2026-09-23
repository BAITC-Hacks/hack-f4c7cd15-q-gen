export const defaults={gid:'',role:'',cluster:'',depth:'',seed:'',boundary:'',q:'',sort:'priority_score',order:'desc',page:'0',mode:'3d',layout:'depth',color:'neutral',hops:'',direction:'all'};
export function readState(){const q=new URLSearchParams(location.search);return Object.fromEntries(Object.entries(defaults).map(([k,v])=>[k,q.get(k)??v]));}
export function writeState(next,{replace=false}={}){const q=new URLSearchParams(location.search);for(const [k,v]of Object.entries(next))if(v===defaults[k]||v===''||v==null)q.delete(k);else q.set(k,String(v));const url=location.pathname+(q.size?'?'+q:'')+location.hash;history[replace?'replaceState':'pushState']({},'',url);try{sessionStorage.setItem('potok-state',JSON.stringify(readState()));}catch{} window.dispatchEvent(new Event('potok-state'));}
export function link(path,extra={}){const u=new URL(path,location.origin);const state=readState();
 for(const [k,v]of Object.entries({...state,...extra}))if(v!==defaults[k]&&v!==''&&v!=null)u.searchParams.set(k,v);else u.searchParams.delete(k);return u.pathname+u.search+u.hash;}
export function neighborhood(data,gid,hops,direction='all'){
 const found=new Set([gid]);let frontier=new Set([gid]);
 for(let i=0;i<hops;i++){const next=new Set();for(const e of data.edges){if(direction!=='in'&&frontier.has(e.src))next.add(e.dst);if(direction!=='out'&&frontier.has(e.dst))next.add(e.src);}frontier=new Set([...next].filter(id=>!found.has(id)));for(const id of next)found.add(id);}return found;
}
export function visibleGraph(data,s){const near=s.gid&&s.hops?neighborhood(data,s.gid,Number(s.hops),s.direction):null;
 const nodes=data.nodes.filter(n=>(!s.role||n.role===s.role)&&(!s.cluster||String(n.cluster_id)===s.cluster)&&(!s.depth||String(n.depth)===s.depth)&&(!s.seed||n.is_seed)&&(!near||near.has(n.gid)));
 const ids=new Set(nodes.map(n=>n.gid));return {nodes,edges:data.edges.filter(e=>ids.has(e.src)&&ids.has(e.dst))};}
export function getReview(){try{return new Set(JSON.parse(sessionStorage.getItem('potok-review')||'[]').filter(x=>typeof x==='string').slice(0,50));}catch{return new Set();}}
export function toggleReview(gid){const set=getReview();if(set.has(gid))set.delete(gid);else{if(set.size>=50)throw Error('В списке уже 50 клиентов. Уберите одного перед добавлением.');set.add(gid);}sessionStorage.setItem('potok-review',JSON.stringify([...set]));window.dispatchEvent(new Event('potok-review'));return set;}
