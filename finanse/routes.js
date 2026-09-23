const form=document.getElementById('route-form'),statusEl=document.getElementById('route-status'),resultEl=document.getElementById('route-result');
const money=n=>new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n/100);
form.addEventListener('submit',async e=>{e.preventDefault();const button=document.getElementById('find-route');button.disabled=true;resultEl.hidden=true;statusEl.textContent='Ищем последовательность переводов…';
 try{const params=new URLSearchParams(new FormData(form));const res=await fetch('/api/routes?'+params);const r=await res.json();if(!res.ok)throw Error(r.error||'Ошибка поиска');
 if(r.status!=='found'){statusEl.textContent=r.status==='limited'?'Достигнут предел поиска. Сузьте период или уменьшите число шагов; отсутствие цепочки не установлено.':'В этих пределах цепочка не найдена. Попробуйте расширить период или увеличить допустимую паузу.';return;}
 resultEl.hidden=false;document.getElementById('route-title').textContent=`Найдена цепочка · переводов: ${r.steps.length}`;
 document.getElementById('route-steps').replaceChildren();document.getElementById('route-chain').replaceChildren();
 const ids=[r.steps[0].src,...r.steps.map(s=>s.dst)];ids.forEach((id,i)=>{if(i){const arrow=document.createElement('span');arrow.className='chain-arrow';arrow.textContent='→';document.getElementById('route-chain').append(arrow)}const a=document.createElement('a');a.className='chain-node';a.href='/analytics?gid='+encodeURIComponent(id);a.textContent=id;document.getElementById('route-chain').append(a)});
 r.steps.forEach((s,i)=>{const tr=document.createElement('tr');[i+1,s.src,s.dst,s.date,money(s.amount_tiyn)].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});document.getElementById('route-steps').append(tr)});
 document.getElementById('route-summary').textContent=`Минимальная сумма отдельной операции в цепочке: ${money(r.bottleneck_tiyn)} ₸. Это не оценка суммы, дошедшей до получателя. Нажмите на gid, чтобы открыть карточку клиента.`;
 statusEl.textContent='Даты возрастают на каждом шаге. Показана одна из кратчайших цепочек в заданных пределах.';
 }catch(e){statusEl.textContent=e.message;}finally{button.disabled=false;}});
(async()=>{try{const res=await fetch('/api/route-example');if(!res.ok)return;const r=await res.json();if(!r.source)return;const b=document.getElementById('example-route');b.disabled=false;b.onclick=()=>{form.elements.source.value=r.source;form.elements.target.value=r.target;form.elements.hops.value='4';form.elements.gap.value='2';form.elements.start.value='';form.elements.end.value='';statusEl.textContent='Пример подставлен из операций выборки. Нажмите «Найти цепочку».';resultEl.hidden=true;};}catch{}})();

