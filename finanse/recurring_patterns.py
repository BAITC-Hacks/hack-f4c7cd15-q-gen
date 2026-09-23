"""Repeated A -> B -> C motifs, using distinct days rather than join multiplicity."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path


def detect(rows, max_gap=2):
    if max_gap not in (1,2):raise ValueError('Supported window: 1 or 2 days')
    pairs=defaultdict(lambda:defaultdict(int))
    for src,dst,day,amount in rows:
        src,dst=str(src),str(dst)
        if src==dst:continue
        pairs[src,dst][date.fromisoformat(str(day))]+=int((Decimal(str(amount))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    incoming=defaultdict(set);outgoing=defaultdict(set)
    for src,dst in pairs:incoming[dst].add(src);outgoing[src].add(dst)
    patterns=[]
    for mid in sorted(set(incoming)&set(outgoing)):
        for src in sorted(incoming[mid]):
            for dst in sorted(outgoing[mid]):
                if src==dst:continue
                ins=sorted(pairs[src,mid].items());outs=sorted(pairs[mid,dst].items())
                cursor=0;matches=[]
                for in_day,in_amount in ins:
                    while cursor<len(outs) and outs[cursor][0]<=in_day:cursor+=1
                    if cursor==len(outs):break
                    out_day,out_amount=outs[cursor]
                    if (out_day-in_day).days>max_gap:continue
                    matches.append(dict(in_date=str(in_day),out_date=str(out_day),lag_days=(out_day-in_day).days,
                        in_tiyn=in_amount,out_tiyn=out_amount))
                    cursor+=1
                if len(matches)>=2:
                    patterns.append(dict(src=src,mid=mid,dst=dst,occurrences=len(matches),
                        first=matches[0]['in_date'],last=matches[-1]['out_date'],events=matches,
                        pair_min_sum_tiyn=sum(min(m['in_tiyn'],m['out_tiyn']) for m in matches)))
    patterns.sort(key=lambda p:(-p['occurrences'],-p['pair_min_sum_tiyn'],p['src'],p['mid'],p['dst']))
    return dict(patterns=patterns,count=len(patterns),max_gap=max_gap,
                method='Distinct input and output days per route; same-day aggregation; chronological greedy pairing; at least two occurrences.')


def run(db_path,out):
    from analyze import duckdb
    with duckdb.connect(str(db_path),read_only=True) as db:
        rows=db.execute('SELECT src,dst,date,sum_kzt FROM transactions ORDER BY date,src,dst').fetchall()
    report=detect(rows)
    report['transactions']=len(rows)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    return report


if __name__=='__main__':
    root=Path(__file__).resolve().parent
    print('Recurring routes:',run(root/'out/analytics.duckdb',root/'out/patterns.json')['count'])
