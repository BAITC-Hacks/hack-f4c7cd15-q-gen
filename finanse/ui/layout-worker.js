import {computeLayout} from './layout-core.js';
const cache=new Map();self.onmessage=({data:{id,nodes,mode}})=>{try{if(!cache.has(mode))cache.set(mode,computeLayout(nodes,mode));self.postMessage({id,positions:cache.get(mode)});}catch(e){self.postMessage({id,error:e.message});}};
