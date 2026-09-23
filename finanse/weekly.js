const W=id=>document.getElementById(id),nf=n=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(n);
const safe=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const signed=n=>(n>0?'+':'')+nf(n),percent=x=>x.pct===null?(x.after?'Нет базы':'—'):signed(x.pct)+'%';
let weeks=[],comparison=null,weekPage=0;
function period(w){return `${w.start.slice(5)} — ${w.end.slice(5)} · ${w.days} дн${w.partial?' (неполная)':''}`;}
function renderWeekly(){
 if(!comparison)return;
 const q=W('weekly-search').value.trim(),direction=W('weekly-direction').value,sort=W('weekly-sort').value;
 const clients=comparison.clients.filter(n=>n.gid.includes(q)&&(direction==='all'||direction==='growth'&&n.amount.delta>0||direction==='decline'&&n.amount.delta<0||direction==='appeared'&&n.amount.status==='appeared'));
 clients.sort((a,b)=>sort==='peers'?b.new_peers-a.new_peers:Math.abs(b[sort==='transactions'?'transactions':'amount'].delta)-Math.abs(a[sort==='transactions'?'transactions':'amount'].delta));
 W('weekly-clients').innerHTML=clients.slice(weekPage*25,weekPage*25+25).map(n=>`<tr><td><a href="/analytics?gid=${encodeURIComponent(n.gid)}">${safe(n.gid)} ↗</a></td><td>${nf(n.amount.before)}</td><td>${nf(n.amount.after)}</td><td>${signed(n.amount.delta)}</td><td>${percent(n.amount)}</td><td>${nf(n.transactions.before)} → ${nf(n.transactions.after)}</td><td>${n.before_peers} → ${n.after_peers}</td><td>+${n.new_peers} / −${n.lost_peers}</td></tr>`).join('')||'<tr><td colspan="8">Нет клиентов с такими условиями. Клиенты без операций в обеих неделях не показаны.</td></tr>';
 W('weekly-count').textContent=`Найдено: ${clients.length}`;W('weekly-page').textContent=clients.length?`${weekPage*25+1}–${Math.min(weekPage*25+25,clients.length)} из ${clients.length}`:'Нет результатов';W('weekly-prev').disabled=weekPage===0;W('weekly-next').disabled=(weekPage+1)*25>=clients.length;
}
async function loadComparison(){
 const before=W('week-before').value,after=W('week-after').value,mode=W('week-mode').value;
 W('week-submit').disabled=true;W('weekly-result').hidden=true;W('weekly-status').textContent='Сравниваем недели…';
 try{
 const response=await fetch('/api/weekly?'+new URLSearchParams({before,after,mode}));const r=await response.json();if(!response.ok)throw Error(r.error);comparison=r;weekPage=0;
 const daily=mode==='daily',unit=daily?'₸ / день':'₸';
 W('weekly-status').textContent=`База: ${period(r.before)}. Сравнение: ${period(r.after)}. ${daily?'Суммы и операции приведены к одному дню.':'Сравниваются общие суммы; учитывайте разную длину периодов.'}`;
 W('weekly-kpis').innerHTML=[['Оборот · '+unit,nf(r.amount.after),`${nf(r.amount.before)} → ${nf(r.amount.after)}`],['Изменение оборота',percent(r.amount),signed(r.amount.delta)+' '+unit],['Переводы'+(daily?' / день':''),nf(r.transactions.after),`${nf(r.transactions.before)} → ${nf(r.transactions.after)}`],['Активные клиенты',nf(r.active_clients.after),`${nf(r.active_clients.before)} → ${nf(r.active_clients.after)} · без нормировки`]].map(([l,v,t])=>`<div class="card kpi"><label>${l}</label><strong>${v}</strong><small>${t}</small></div>`).join('');
 W('base-heading').textContent='База, '+unit;W('after-heading').textContent='Сравнение, '+unit;
 const amounts=weeks.map(w=>w.amount_tiyn/100/(daily?w.days:1)),max=Math.max(1,...amounts);
 W('weekly-chart-label').textContent='Оборот, '+unit+' · каждая операция в графе учитывается один раз';
 W('weekly-chart').innerHTML=weeks.map((w,i)=>`<div class="weekly-bar-row"><span>${period(w)}</span><div class="track"><div class="fill" style="width:${amounts[i]/max*100}%;background:${w.id===after?'#91ebbd':w.id===before?'#a5a4fb':'#577285'}"></div></div><strong>${nf(amounts[i])}</strong></div>`).join('');
 W('weekly-result').hidden=false;renderWeekly();
 }catch(e){comparison=null;W('weekly-status').textContent=e.message||'Не удалось загрузить сравнение';}finally{W('week-submit').disabled=false;}
}
W('weekly-form').onsubmit=e=>{e.preventDefault();loadComparison();};
for(const id of ['weekly-search','weekly-direction','weekly-sort'])W(id).addEventListener(id==='weekly-search'?'input':'change',()=>{weekPage=0;renderWeekly();});
W('weekly-prev').onclick=()=>{weekPage--;renderWeekly();};W('weekly-next').onclick=()=>{weekPage++;renderWeekly();};
(async()=>{try{const response=await fetch('/api/weekly');const r=await response.json();if(!response.ok)throw Error(r.error);weeks=r.weeks;if(weeks.length<2)throw Error('Для сравнения нужны минимум две недели данных.');for(const w of weeks){W('week-before').add(new Option(period(w),w.id));W('week-after').add(new Option(period(w),w.id));}const full=weeks.filter(w=>!w.partial);const chosen=full.length>=2?full.slice(-2):weeks.slice(-2);W('week-before').value=chosen[0].id;W('week-after').value=chosen[1].id;W('weekly-search').value=new URLSearchParams(location.search).get('gid')||'';await loadComparison();}catch(e){W('weekly-status').textContent=e.message;}})();
