const labels={consolidator:'Сборщик',transit:'Транзит',distributor:'Распределитель',terminal:'Конечный*',coordinator:'Координатор',peripheral:'Периферия / ?'};
const colors={consolidator:'#f7c66e',transit:'#66d5e8',distributor:'#9f97ff',terminal:'#f59bb4',coordinator:'#83e2b2',peripheral:'#8392a8'};
const fmt=n=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(n);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id);
let data,byId,filtered=[],page=0,selected=null;
function render(){
  const q=$('search').value.trim(),role=$('role').value,cluster=$('cluster').value,boundary=$('boundary').value;
  filtered=data.nodes.filter(n=>n.gid.includes(q)&&(!role||n.role===role)&&(cluster===''||String(n.cluster_id)===cluster)&&(boundary!=='exclude'||!n.truncated_by_depth)&&(boundary!=='only'||n.truncated_by_depth));
  $('nodes').innerHTML=filtered.slice(page*20,page*20+20).map(n=>`<tr tabindex="0" data-gid="${n.gid}"><td>${n.gid}${n.is_seed?' <span class="badge">seed</span>':''}${n.truncated_by_depth?' †':''}</td><td style="color:${colors[n.role]}">${labels[n.role]}</td><td>${fmt(n.in_kzt)}</td><td>${fmt(n.out_kzt)}</td><td>${n.in_deg} / ${n.out_deg}</td><td>${n.priority_score.toFixed(3)}</td><td>${n.cluster_id}</td></tr>`).join('');
  $('count').textContent=filtered.length?`${page*20+1}–${Math.min(page*20+20,filtered.length)} из ${fmt(filtered.length)} участников`:'Нет участников по заданным фильтрам';
  $('prev').disabled=page===0;$('next').disabled=(page+1)*20>=filtered.length;
}
function drawGraph(){
  if(!selected)return;
  const n=byId.get(selected),mode=$('graph-mode').value,limit=$('graph-limit').value;
  let edges=data.edges.filter(e=>mode==='cluster'?byId.get(e.src).cluster_id===n.cluster_id&&byId.get(e.dst).cluster_id===n.cluster_id:e.src===selected||e.dst===selected).sort((a,b)=>b.sum_kzt-a.sum_kzt);
  const total=edges.length;if(limit!=='all')edges=edges.slice(0,Number(limit));
  const ids=[...new Set([selected,...edges.flatMap(e=>[e.src,e.dst])])],other=ids.filter(id=>id!==selected),pos={[selected]:[500,250]};
  other.forEach((id,i)=>{const ring=Math.floor(i/32),count=Math.min(32,other.length-ring*32),angle=2*Math.PI*(i%32)/count;pos[id]=[500+(210+ring*65)*Math.cos(angle),250+(110+ring*35)*Math.sin(angle)]});
  const clusterMode=$('graph-color').value==='cluster';
  const color=id=>clusterMode?`hsl(${byId.get(id).cluster_id*137.508%360} 65% 68%)`:colors[byId.get(id).role];
  let svg='<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="10" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#8dabc9"/></marker></defs>';
  for(const e of edges){const a=pos[e.src],b=pos[e.dst];const path=e.src===e.dst?`M${a[0]} ${a[1]-8} C${a[0]-40} ${a[1]-55},${a[0]+40} ${a[1]-55},${a[0]+8} ${a[1]}`:`M${a[0]} ${a[1]} Q${(a[0]+b[0])/2+(b[1]-a[1])*.06} ${(a[1]+b[1])/2-(b[0]-a[0])*.06} ${b[0]} ${b[1]}`;svg+=`<path d="${path}" fill="none" stroke="#7894b1" stroke-opacity=".6" stroke-width="1.3" marker-end="url(#arrow)"><title>${e.src} → ${e.dst}: ${fmt(e.sum_kzt)} ₸; ${e.n_tx} операций</title></path>`;}
  for(const id of ids){const [x,y]=pos[id],r=byId.get(id);svg+=`<g data-node="${id}" tabindex="0" role="button" aria-label="Клиент ${id}, ${labels[r.role]}, группа ${r.cluster_id}"><circle cx="${x}" cy="${y}" r="${id===selected?13:7}" fill="${color(id)}" stroke="${id===selected?'white':'#182337'}" stroke-width="2"><title>${id} · ${labels[r.role]} · группа ${r.cluster_id}</title></circle>${ids.length<=24||id===selected?`<text x="${x}" y="${y+24}" fill="#dce6f6" text-anchor="middle" font-size="10">…${id.slice(-9)}</text>`:''}</g>`;}
  $('network').innerHTML=svg;
  const xs=ids.map(id=>pos[id][0]),ys=ids.map(id=>pos[id][1]);
  const left=Math.min(0,...xs)-40,top=Math.min(0,...ys)-40;
  const width=Math.max(1000,...xs)+40-left,height=Math.max(500,...ys)+40-top;
  $('network').setAttribute('viewBox',`${left} ${top} ${width} ${height}`);
  $('graph-info').textContent=`Показано ${edges.length} из ${total} связей · ${ids.length} клиентов. Нажмите на узел для перехода. Стрелки — направление переводов.`;
  $('graph-legend').innerHTML=clusterMode?[...new Set(ids.map(id=>byId.get(id).cluster_id))].sort((a,b)=>a-b).map(c=>`<span style="color:hsl(${c*137.508%360} 65% 68%)">● Группа ${c}</span>`).join(' '):Object.entries(labels).map(([k,v])=>`<span style="color:${colors[k]}">● ${v}</span>`).join(' ');
}
function detail(gid,scroll=true){
  selected=gid;const n=byId.get(gid);$('details').classList.add('visible');$('details').open=true;
  $('detail-title').textContent=`Клиент ${gid} · ${labels[n.role]}`;
  $('detail-text').innerHTML=`<strong>Почему эта роль:</strong> ${esc(n.evidence)}<br><strong>Почему такой приоритет:</strong> ${esc(n.priority_evidence)}<br>Сила правила: ${n.role_score.toFixed(2)}. Устойчивость роли при трёх настройках порогов: ${(n.role_stability*100).toFixed(0)}%. Это не вероятность виновности.<br>Достижим от ${n.seed_reach} разных seed за ≤4 шага; соседние внешние группы: ${n.neighbor_clusters}. Активных дней: ${n.active_days}.<br><strong>Сценарий транзита 1–2 дня:</strong> ${fmt(n.fast_matched_kzt)} ₸ (${(n.fast_share*100).toFixed(1)}% наблюдаемого входа), ${n.fast_windows} сопоставлений дней. Каждая сумма распределяется один раз; переводы одного дня не упорядочиваются.<br><strong>Что запросить:</strong> ${n.truncated_by_depth?'продолжение исходящих переводов за четвёртым шагом':n.is_seed?'полную историю входящих переводов seed':'точное время, назначение переводов и операции вне выборки'}.`;
  const windows=data.temporal_matches.filter(m=>m.gid===gid).sort((a,b)=>b.amount_tiyn-a.amount_tiyn).slice(0,8);
  $('temporal-table').innerHTML=windows.length?windows.map(m=>`<tr><td>${m.in_date}</td><td>${m.out_date}</td><td>${m.lag_days}</td><td>${fmt(m.amount_tiyn/100)}</td></tr>`).join(''):'<tr><td colspan="4">Нет сопоставлений через 1–2 дня</td></tr>';
  const edges=data.edges.filter(e=>e.src===gid||e.dst===gid).sort((a,b)=>b.sum_kzt-a.sum_kzt);
  $('connections').innerHTML=edges.map(e=>`<tr data-gid="${e.src===gid?e.dst:e.src}" tabindex="0"><td>${e.src}</td><td>→ ${e.dst}</td><td>${fmt(e.sum_kzt)}</td><td>${e.n_tx}</td></tr>`).join('')||'<tr><td colspan="4">Наблюдаемых связей нет</td></tr>';
  drawGraph();if(scroll)$('details').scrollIntoView({behavior:'smooth',block:'start'});
}
async function init(){try{
  const res=await fetch('/api/analytics');if(!res.ok)throw Error('Выполните python analyze.py для подготовки данных.');data=await res.json();byId=new Map(data.nodes.map(n=>[n.gid,n]));
  const s=data.summary;$('kpis').innerHTML=[['Оборот выборки',fmt(s.total_kzt)+' ₸','Сумма переводов, не уникальный капитал'],['Участники',fmt(s.nodes),`${s.seeds} seed · ${s.isolates} без связей`],['Транзакции',fmt(s.transactions),`${fmt(s.edges)} направленных связей`],['Пересчёт',s.runtime_seconds+' с',`${s.clusters} сообществ · локально`]].map(([l,v,t])=>`<div class="card kpi"><label>${l}</label><strong>${v}</strong><small>${t}</small></div>`).join('');
  $('period').textContent=`${s.start} — ${s.end} · KZT`;
  const max=Math.max(...data.daily.map(d=>d.sum_kzt));$('daily').innerHTML=data.daily.map(d=>`<div class="bar" style="height:${Math.max(1,d.sum_kzt/max*100)}%" title="${d.day}: ${fmt(d.sum_kzt)} ₸ · ${d.n_tx} переводов"></div>`).join('');
  $('roles').innerHTML=Object.entries(labels).map(([key,label])=>{const count=data.nodes.filter(n=>n.role===key).length;return `<div class="role-row"><span style="color:${colors[key]}">${label}</span><div class="track"><div class="fill" style="background:${colors[key]};width:${count/s.nodes*100}%"></div></div><span>${fmt(count)}</span></div>`}).join('');
  $('limits').textContent=`Порог 5 000 ₸ · только исходящий обход · 4 шага. У ${s.truncated} клиентов (†) граф обрывается: конечная роль неизвестна. Входящие seed неполны. Все роли — гипотезы для проверки.`;
  for(const [v,l] of Object.entries(labels))$('role').add(new Option(l,v));for(const c of data.clusters)$('cluster').add(new Option(`Группа ${c.cluster_id} · ${c.n_nodes} чел.`,c.cluster_id));
  $('clusters').innerHTML=[...data.clusters].sort((a,b)=>b.sum_kzt_internal-a.sum_kzt_internal).map(c=>`<tr><td>${c.cluster_id}</td><td>${c.n_nodes}</td><td>${c.n_seed}</td><td>${fmt(c.sum_kzt_internal)}</td><td class="wrap">${esc(c.hypothesis)}</td></tr>`).join('');
  $('demo-cases').innerHTML=data.demo.map(d=>`<button data-gid="${d.gid}"><strong style="color:${colors[d.role]}">${labels[d.role]}</strong><br><small>${d.gid}</small><p>${esc(d.evidence)}</p></button>`).join('');
  $('resilience').innerHTML=data.resilience.map(r=>`<tr><td>Топ-${r.removed_count}</td><td>${r.baseline_largest} → ${r.largest_component}</td><td>${r.components}</td><td>${r.isolates}</td><td>${fmt(r.random_largest_median)} (${r.random_largest_min}–${r.random_largest_max})</td></tr>`).join('');
  render();
  const requested=new URLSearchParams(location.search).get('gid');
  if(requested&&byId.has(requested))detail(requested);
}catch(e){$('error').textContent=e.message;}}
$('search').addEventListener('input',()=>{page=0;if(data)render()});
for(const id of ['role','cluster','boundary'])$(id).addEventListener('change',()=>{page=0;if(data)render()});
for(const id of ['graph-mode','graph-limit','graph-color'])$(id).addEventListener('change',drawGraph);
$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};
for(const id of ['nodes','demo-cases','connections']){const select=e=>{const row=e.target.closest('[data-gid]');if(row)detail(row.dataset.gid)};$(id).onclick=select;$(id).onkeydown=e=>{if(e.key==='Enter')select(e)}}
$('network').onclick=e=>{const node=e.target.closest('[data-node]');if(node)detail(node.dataset.node,false)};
$('network').onkeydown=e=>{if(e.key==='Enter'){const node=e.target.closest('[data-node]');if(node)detail(node.dataset.node,false)}};
init();

(async()=>{try{const res=await fetch('/api/controls');if(!res.ok)throw Error('Контрольные сценарии ещё не рассчитаны: python control_scenarios.py');const report=await res.json();$('control-count').textContent=`${report.passed} из ${report.total} проверок пройдено · раскрыть`;$('control-rows').innerHTML=report.cases.map(c=>`<tr><td>${esc(c.name)}</td><td>${labels[c.expected]}</td><td>${labels[c.actual]}</td><td style="color:${c.passed?'#91ebbd':'#ffb3b3'}">${c.passed?'PASS':'FAIL'}</td><td class="wrap">${esc(c.reason)}</td></tr>`).join('');$('control-limits').textContent=report.limitation;}catch(e){$('control-count').textContent='Нет отчёта';$('control-limits').textContent=e.message;}})();
function openAnchor(){const target=document.getElementById(location.hash.slice(1));if(target){if(target.tagName==='DETAILS')target.open=true;const parent=target.closest('details');if(parent)parent.open=true;}}
window.addEventListener('hashchange',openAnchor);openAnchor();

