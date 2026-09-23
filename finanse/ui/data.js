export const roles={consolidator:'Сборщик',transit:'Транзит',distributor:'Распределитель',terminal:'Конечный (гипотеза)',coordinator:'Координатор',peripheral:'Периферия / не определена'};
export const roleColors={consolidator:'#a76d21',transit:'#217f95',distributor:'#7555ab',terminal:'#b05269',coordinator:'#53648d',peripheral:'#78817c'};
export const fmt=(n,d=0)=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:d}).format(n);
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let promise;
export function normalize(d){
 if(!d.summary||!Array.isArray(d.nodes)||!Array.isArray(d.edges))throw Error('Неверная структура ответа /api/analytics. Пересчитайте данные: python run.py.');
 for(const n of d.nodes)if(typeof n.gid!=='string')throw Error('gid должен приходить строкой: точность идентификатора не гарантирована.');
 const byId=new Map(d.nodes.map(n=>[n.gid,n]));
 if(byId.size!==d.nodes.length)throw Error('В данных есть повторяющиеся gid.');
 for(const e of d.edges)if(typeof e.src!=='string'||typeof e.dst!=='string'||!byId.has(e.src)||!byId.has(e.dst))throw Error('Некорректные идентификаторы связи.');
 return {...d,byId};
}
export function loadData(){return promise??=fetch('/api/analytics').then(async r=>{if(!r.ok)throw Error(`Данные недоступны (HTTP ${r.status}). Выполните python run.py и повторите загрузку.`);return normalize(await r.json());}).catch(e=>{promise=null;throw e;});}
export async function loadControls(){const r=await fetch('/api/controls');if(!r.ok)throw Error(`Контрольные сценарии недоступны (HTTP ${r.status}). Выполните python control_scenarios.py.`);return r.json();}
