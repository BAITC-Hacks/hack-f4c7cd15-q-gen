import {shell} from './shell.js';
import {readState} from './state.js';
shell('Цепочки',4);
const form=document.getElementById('route-form');
const restore=()=>{const q=new URLSearchParams(location.search);for(const key of ['source','target','hops','gap','start','end'])if(q.has('route_'+key))form.elements[key].value=q.get('route_'+key);if(!q.has('route_source'))form.elements.source.value=readState().gid;};restore();
form.addEventListener('submit',()=>{const url=new URL(location.href);for(const [k,v]of new FormData(form))if(v)url.searchParams.set('route_'+k,v);else url.searchParams.delete('route_'+k);history.pushState({},'',url.pathname+url.search);},true);
window.addEventListener('popstate',()=>{form.reset();restore();document.getElementById('route-result').hidden=true;document.getElementById('route-status').textContent='Параметры восстановлены. Нажмите «Найти цепочку».';});
