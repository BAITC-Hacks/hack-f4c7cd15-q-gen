const num=n=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(n);
(async()=>{try{
 const res=await fetch('/api/analytics');if(!res.ok)throw Error('Не удалось загрузить данные. Выполните python run.py.');
 const d=await res.json(),s=d.summary;
 document.getElementById('home-period').textContent=`${s.start} — ${s.end} · KZT · анализ работает локально`;
 document.getElementById('home-kpis').innerHTML=[['Участники',num(s.nodes),'Клиенты в графе'],['Переводы',num(s.transactions),`${num(s.edges)} направленных связей`],['Оборот выборки',num(s.total_kzt)+' ₸','Сумма операций, не уникальный капитал'],['Сообщества',num(s.clusters),'Группы по структуре переводов']].map(([l,v,t])=>`<div class="card kpi"><label>${l}</label><strong>${v}</strong><small>${t}</small></div>`).join('');
 const center=d.nodes.reduce((a,b)=>a.priority_score>b.priority_score?a:b),edges=d.edges.filter(e=>e.src===center.gid||e.dst===center.gid).sort((a,b)=>b.sum_kzt-a.sum_kzt).slice(0,12);
 const ids=[...new Set(edges.flatMap(e=>[e.src,e.dst]))].filter(x=>x!==center.gid),pos={[center.gid]:[250,175]};ids.forEach((id,i)=>{const a=i*2*Math.PI/ids.length;pos[id]=[250+185*Math.cos(a),175+130*Math.sin(a)]});
 let svg='<defs><marker id="ha" markerWidth="6" markerHeight="6" refX="12" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#82e4b5"/></marker></defs>';
 for(const e of edges){const a=pos[e.src],b=pos[e.dst];svg+=`<path d="M${a} L${b}" stroke="#82e4b5" stroke-opacity=".45" marker-end="url(#ha)"/>`}
 for(const [id,[x,y]]of Object.entries(pos))svg+=`<circle cx="${x}" cy="${y}" r="${id===center.gid?20:7}" fill="${id===center.gid?'#82e4b5':'#929cf7'}"><title>${id}</title></circle>`;
 document.getElementById('hero-network').innerHTML=svg;document.getElementById('hero-caption').textContent=`Клиент ${center.gid} · ${edges.length} крупнейших связей`;
}catch(e){document.getElementById('error').textContent=e.message;document.getElementById('home-period').textContent='Данные пока недоступны';}})();

