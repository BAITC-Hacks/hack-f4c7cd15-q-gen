export class Layout{
 constructor(nodes){this.nodes=nodes;this.cache=new Map();this.pending=new Map();this.id=0;this.worker=new Worker(new URL('./layout-worker.js',import.meta.url),{type:'module'});this.worker.onmessage=({data})=>{const p=this.pending.get(data.id);if(p){this.pending.delete(data.id);data.error?p.reject(Error(data.error)):p.resolve(data.positions);}};this.worker.onerror=()=>{for(const p of this.pending.values())p.reject(Error('Не удалось рассчитать раскладку. Повторите загрузку.'));this.pending.clear();};}
 get(mode){if(!this.cache.has(mode))this.cache.set(mode,new Promise((resolve,reject)=>{const id=++this.id;this.pending.set(id,{resolve,reject});this.worker.postMessage({id,nodes:this.nodes,mode});}));return this.cache.get(mode);}
 dispose(){this.worker.terminate();this.pending.clear();this.cache.clear();}
}
