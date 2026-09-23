"""Export analyst-selected clients with reasons, without changing source data."""
import csv
import io


def export_review(analytics, gids):
    selected=set(gids)
    if not selected or len(selected)>50:
        raise ValueError('Выберите от 1 до 50 клиентов')
    nodes={str(n['gid']):n for n in analytics['nodes']}
    if not selected.issubset(nodes):
        raise ValueError('В списке есть клиент, отсутствующий в текущем расчёте')
    fields=['gid','role','role_score','role_stability','priority_score','evidence',
            'priority_evidence','in_kzt','out_kzt','seed_reach','next_data_request','limitation']
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    for gid in sorted(selected,key=lambda x:(-nodes[x]['priority_score'],x)):
        n=nodes[gid]
        row={key:n[key] for key in fields if key in n}
        row['gid']=gid
        row['next_data_request']=('Продолжение исходящих за 4-м шагом' if n['truncated_by_depth']
            else 'Полные входящие seed' if n['is_seed']
            else 'Точное время, назначение платежей, остатки и операции вне выборки')
        row['limitation']='Роль — гипотеза; score не является вероятностью виновности; клиент выбран аналитиком'
        writer.writerow(row)
    return '\ufeff'+output.getvalue()

