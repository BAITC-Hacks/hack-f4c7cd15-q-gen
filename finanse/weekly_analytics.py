"""Calendar-week activity; partial weeks compared using observed calendar days."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path


def summarize(rows, start, end):
    start,end=date.fromisoformat(str(start)),date.fromisoformat(str(end))
    if end<start:raise ValueError('Invalid period')
    weeks={}
    monday=start-timedelta(days=start.weekday())
    while monday<=end:
        left,right=max(start,monday),min(end,monday+timedelta(days=6))
        weeks[monday.isoformat()]=dict(id=monday.isoformat(),start=str(left),end=str(right),
            days=(right-left).days+1,partial=left!=monday or right!=monday+timedelta(days=6),
            amount_tiyn=0,n_tx=0,clients={})
        monday+=timedelta(days=7)
    for src,dst,day,amount in rows:
        day=date.fromisoformat(str(day))
        if not start<=day<=end:raise ValueError('Transaction outside period')
        key=(day-timedelta(days=day.weekday())).isoformat()
        week=weeks[key]
        value=int((Decimal(str(amount))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if value<=0:raise ValueError('Non-positive amount')
        src,dst=str(src),str(dst)
        week['amount_tiyn']+=value;week['n_tx']+=1
        for gid in {src,dst}:
            n=week['clients'].setdefault(gid,dict(amount_tiyn=0,n_tx=0,in_tiyn=0,out_tiyn=0,peers=set()))
            n['amount_tiyn']+=value;n['n_tx']+=1
            if gid==src:n['out_tiyn']+=value
            if gid==dst:n['in_tiyn']+=value
            if src!=dst:n['peers'].add(dst if gid==src else src)
    for w in weeks.values():
        w['active_clients']=len(w['clients'])
        for n in w['clients'].values():n['peers']=sorted(n['peers'])
    return dict(start=str(start),end=str(end),weeks=list(weeks.values()))


def change(before,after):
    return dict(before=before,after=after,delta=after-before,
                pct=(after/before-1)*100 if before else None,
                status='appeared' if not before and after else 'inactive' if before and not after else 'changed' if before!=after else 'same')


def compare(report,before_id,after_id,mode='daily'):
    periods={w['id']:w for w in report['weeks']}
    if before_id not in periods or after_id not in periods:raise ValueError('Выберите недели из списка')
    if before_id>=after_id:raise ValueError('Базовая неделя должна быть раньше сравниваемой')
    if mode not in ('daily','total'):raise ValueError('Неизвестный режим сравнения')
    a,b=periods[before_id],periods[after_id]
    da,db=(a['days'],b['days']) if mode=='daily' else (1,1)
    empty=dict(amount_tiyn=0,n_tx=0,in_tiyn=0,out_tiyn=0,peers=[])
    result=[]
    for gid in sorted(set(a['clients'])|set(b['clients'])):
        x,y=a['clients'].get(gid,empty),b['clients'].get(gid,empty)
        result.append(dict(gid=gid,amount=change(x['amount_tiyn']/100/da,y['amount_tiyn']/100/db),
            transactions=change(x['n_tx']/da,y['n_tx']/db),
            before_peers=len(x['peers']),after_peers=len(y['peers']),
            new_peers=len(set(y['peers'])-set(x['peers'])),lost_peers=len(set(x['peers'])-set(y['peers'])),
            before_total_kzt=x['amount_tiyn']/100,after_total_kzt=y['amount_tiyn']/100))
    result.sort(key=lambda n:(-abs(n['amount']['delta']),n['gid']))
    metadata=lambda w:{k:v for k,v in w.items() if k!='clients'}
    return dict(before=metadata(a),after=metadata(b),mode=mode,clients=result,
        amount=change(a['amount_tiyn']/100/da,b['amount_tiyn']/100/db),
        transactions=change(a['n_tx']/da,b['n_tx']/db),
        active_clients=change(a['active_clients'],b['active_clients']))


def run(db_path,out):
    from analyze import duckdb
    with duckdb.connect(str(db_path),read_only=True) as db:
        start,end=db.execute('SELECT min(date),max(date) FROM transactions').fetchone()
        report=summarize(db.execute('SELECT src,dst,date,sum_kzt FROM transactions').fetchall(),start,end)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    return report


if __name__=='__main__':
    root=Path(__file__).resolve().parent
    r=run(root/'out/analytics.duckdb',root/'out/weekly.json')
    print('Weekly periods:',len(r['weeks']))
