"""Local, reproducible analytics for the supplied transfer graph."""
import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.packages'))
import duckdb
import networkx as nx
from graph_insights import enrich, assign_priority, resilience, cluster_description


def rows(db, sql):
    cur = db.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def pagerank(graph):
    # Weighted directed PageRank, including isolates; no scipy dependency.
    n = len(graph)
    p = dict.fromkeys(graph, 1 / n)
    totals = dict(graph.out_degree(weight='weight'))
    for _ in range(1000):
        base = (0.15 + 0.85 * sum(p[u] for u in graph if totals[u] == 0)) / n
        q = dict.fromkeys(graph, base)
        for u, v, d in graph.edges(data=True):
            q[v] += 0.85 * p[u] * d['weight'] / totals[u]
        if sum(abs(q[u] - p[u]) for u in graph) < 1e-10:
            return q
        p = q
    raise RuntimeError('PageRank did not converge')


def classify(r, sensitivity=1.0):
    # Scores are rule strength, not calibrated probabilities.
    if r['in_deg'] == r['out_deg'] == 0:
        return 'peripheral', 0.3, 'нет наблюдаемых связей'
    if r['truncated_by_depth']:
        return 'peripheral', 0.2, 'граница выгрузки; роль неизвестна'
    if (r['in_deg'] >= 5*sensitivity and r['out_deg'] >= 5*sensitivity
            and r.get('seed_reach',0)>=2 and r.get('neighbor_clusters',0)>=2):
        return 'coordinator', 0.75, f"связь с {r['seed_reach']} seed и {r['neighbor_clusters']} внеш. группами"
    if r['out_deg'] >= 5*sensitivity and r['out_deg'] >= 2*sensitivity * r['in_deg']:
        return 'distributor', 0.8, 'рассылка многим получателям'
    if (not r['is_seed'] and r['in_deg'] >= 3*sensitivity
            and r['in_deg'] >= 2*sensitivity * r['out_deg']
            and r['in_kzt']>0 and r['out_kzt']/r['in_kzt']<=.5/sensitivity):
        return 'consolidator', 0.75, f"сбор; выход {r['out_kzt']/r['in_kzt']:.0%} наблюдаемого входа"
    if (not r['is_seed'] and r['in_kzt'] > 0 and r['out_deg'] > 0
            and 1-0.3/sensitivity <= r['pass_through'] <= 1+0.3/sensitivity
            and r.get('fast_share',0)>=.5*sensitivity):
        return 'transit', 0.65, f"вход≈выход; сценарий 1–2д {r['fast_share']:.0%} входа"
    if not r['is_seed'] and r['in_deg'] > 0 and r['out_deg'] == 0:
        return 'terminal', 0.55, 'нет выхода в наблюдаемой выборке'
    return 'peripheral', 0.4, 'недостаточно признаков других ролей'


def export_csv(path, data):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def run(data, out):
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect(str(out / 'analytics.duckdb'))
    db.execute("SET memory_limit='1GB'")
    db.execute('BEGIN TRANSACTION')
    try:
        for table in ('nodes', 'edges', 'transactions'):
            path = str((data / (table + '.parquet')).resolve()).replace("'", "''")
            db.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
        checks = {
            'unique_nodes': 'SELECT count(*)-count(DISTINCT gid) FROM nodes',
            'unique_edges': 'SELECT count(*) FROM (SELECT src,dst FROM edges GROUP BY ALL HAVING count(*)>1)',
            'valid_nodes': 'SELECT count(*) FROM nodes WHERE gid IS NULL OR depth IS NULL OR is_seed IS NULL OR depth NOT BETWEEN 0 AND 4',
            'valid_edges': 'SELECT count(*) FROM edges WHERE src IS NULL OR dst IS NULL OR sum_kzt IS NULL OR NOT isfinite(sum_kzt) OR sum_kzt<=0 OR n_tx IS NULL OR n_tx<1',
            'known_endpoints': 'SELECT count(*) FROM edges e LEFT JOIN nodes a ON e.src=a.gid LEFT JOIN nodes b ON e.dst=b.gid WHERE a.gid IS NULL OR b.gid IS NULL',
            'valid_transactions': "SELECT count(*) FROM transactions WHERE src IS NULL OR dst IS NULL OR date IS NULL OR sum_kzt IS NULL OR NOT isfinite(sum_kzt) OR sum_kzt<5000 OR date NOT BETWEEN DATE '2026-07-01' AND DATE '2026-07-31'",
            'edge_reconciliation': '''SELECT count(*) FROM edges e FULL OUTER JOIN
              (SELECT src,dst,sum(sum_kzt) amount,count(*) n FROM transactions GROUP BY src,dst) t
              USING(src,dst) WHERE e.src IS NULL OR t.src IS NULL OR abs(e.sum_kzt-t.amount)>0.01 OR e.n_tx<>t.n''',
        }
        validation = {name: db.execute(sql).fetchone()[0] for name, sql in checks.items()}
        if any(validation.values()):
            raise ValueError(f'Data validation failed: {validation}')
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise
    db.execute('''CREATE OR REPLACE VIEW node_metrics AS
      WITH incoming AS (SELECT dst gid,count(*) in_deg,sum(sum_kzt) in_kzt,sum(n_tx) in_tx FROM edges GROUP BY dst),
      outgoing AS (SELECT src gid,count(*) out_deg,sum(sum_kzt) out_kzt,sum(n_tx) out_tx FROM edges GROUP BY src)
      SELECT n.*,coalesce(in_deg,0) in_deg,coalesce(out_deg,0) out_deg,
      coalesce(in_kzt,0) in_kzt,coalesce(out_kzt,0) out_kzt,
      coalesce(in_tx,0)::BIGINT in_tx,coalesce(out_tx,0)::BIGINT out_tx
      FROM nodes n LEFT JOIN incoming USING(gid) LEFT JOIN outgoing USING(gid)''')
    metrics = rows(db, 'SELECT * FROM node_metrics ORDER BY gid')
    edges = rows(db, 'SELECT * FROM edges ORDER BY src,dst')
    graph = nx.DiGraph()
    graph.add_nodes_from(r['gid'] for r in metrics)
    for e in edges:
        graph.add_edge(e['src'], e['dst'], weight=e['sum_kzt'])
    pr = pagerank(graph)
    # Sum both directions explicitly in the undirected clustering projection.
    ug = nx.Graph()
    ug.add_nodes_from(graph)
    for e in edges:
        a, b = e['src'], e['dst']
        prior = ug.get_edge_data(a, b, {}).get('weight', 0)
        ug.add_edge(a, b, weight=prior + e['sum_kzt'])
    communities = sorted(nx.community.louvain_communities(ug, weight='weight', seed=42), key=lambda s: min(s))
    membership = {gid: i for i, group in enumerate(communities) for gid in group}
    temporal_matches = enrich(graph,metrics,membership,db.execute(
        'SELECT src,dst,date,sum_kzt FROM transactions ORDER BY date,src,dst').fetchall())
    cyclic = set().union(*(s for s in nx.strongly_connected_components(graph) if len(s) > 1))
    cyclic.update(nx.nodes_with_selfloops(graph))
    temporal = rows(db, '''WITH activity AS (
      SELECT src gid,date,sum_kzt FROM transactions UNION ALL SELECT dst,date,sum_kzt FROM transactions),
      days AS (SELECT gid,date,count(*) n FROM activity GROUP BY gid,date)
      SELECT gid,count(*) active_days,max(n)::DOUBLE/sum(n) peak_day_share FROM days GROUP BY gid''')
    times = {r['gid']: r for r in temporal}
    for r in metrics:
        gid = r['gid']
        r['pagerank'] = pr[gid]
        r['pass_through'] = r['out_kzt'] / r['in_kzt'] if r['in_kzt'] else 0.0
        r['pass_through_defined'] = r['in_kzt'] > 0
        r['truncated_by_depth'] = r['depth'] == 4 and r['out_deg'] == 0
        r['cluster_id'] = membership[gid]
        r['cycle_member'] = gid in cyclic
        r['active_days'] = times.get(gid, {}).get('active_days', 0)
        r['peak_day_share'] = times.get(gid, {}).get('peak_day_share', 0.0)
        role, score, reason = classify(r)
        r['role'], r['role_score'] = role, score
        r['role_stability'] = sum(classify(r,s)[0]==role for s in (.8,1,1.2))/3
        r['evidence'] = (f"in={r['in_deg']}/{r['in_kzt']:.0f} KZT; out={r['out_deg']}/{r['out_kzt']:.0f} KZT; "
                         f"tx={r['in_tx']}/{r['out_tx']}; d={r['depth']}; {reason}")[:200]
    assign_priority(metrics)
    ranked = sorted(metrics, key=lambda r: (-r['priority_score'], r['gid']))
    robustness = resilience(graph,ranked)
    cluster_rows = []
    for i, group in enumerate(communities):
        members = [r for r in ranked if r['gid'] in group]
        internal = sum(e['sum_kzt'] for e in edges if e['src'] in group and e['dst'] in group)
        cluster_rows.append(dict(cluster_id=i, n_nodes=len(group), n_seed=sum(r['is_seed'] for r in members),
            sum_kzt_internal=internal, top_gids=';'.join(str(r['gid']) for r in members[:5]),
            **cluster_description(group,members,edges)))
    top = [dict(rank=i+1,gid=r['gid'],role=r['role'],priority_score=r['priority_score'],why=r['priority_evidence']) for i,r in enumerate(ranked[:50])]
    export_csv(out / 'nodes_roles.csv', metrics)
    export_csv(out / 'clusters.csv', cluster_rows)
    export_csv(out / 'top_nodes.csv', top)
    with (out/'temporal_matches.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=['gid','in_date','out_date','lag_days','amount_tiyn'])
        writer.writeheader()
        writer.writerows(temporal_matches)
    for name in ('nodes_roles', 'clusters', 'top_nodes'):
        path = str((out / (name + '.csv')).resolve()).replace("'", "''")
        db.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv_auto('{path}')")
    daily = rows(db, 'SELECT date::VARCHAR AS "day",count(*) n_tx,sum(sum_kzt) sum_kzt FROM transactions GROUP BY date ORDER BY date')
    summary = dict(nodes=len(metrics), edges=len(edges), transactions=db.execute('SELECT count(*) FROM transactions').fetchone()[0],
        total_kzt=sum(e['sum_kzt'] for e in edges), seeds=sum(r['is_seed'] for r in metrics),
        clusters=len(communities), truncated=sum(r['truncated_by_depth'] for r in metrics), cycle_nodes=len(cyclic),
        start=daily[0]['day'], end=daily[-1]['day'],
        weak_components=nx.number_weakly_connected_components(graph),isolates=nx.number_of_isolates(graph))
    # IDs exceed JavaScript's exact integer range: stringify before sending to browser.
    ui_nodes = [{**r, 'gid': str(r['gid'])} for r in ranked]
    ui_edges = [{**e, 'src': str(e['src']), 'dst': str(e['dst'])} for e in edges]
    # Demo cases selected by rules, never by a hardcoded gid.
    demo = []
    for role in ('consolidator','transit','coordinator'):
        candidates = [r for r in ranked if r['role']==role]
        if candidates:
            best = max(candidates,key=lambda r:(r['fast_matched_kzt'],r['priority_score'])) if role=='transit' else candidates[0]
            demo.append(dict(gid=str(best['gid']),role=role,evidence=best['evidence'],
                             priority_evidence=best['priority_evidence'],fast_share=best['fast_share']))
    summary['runtime_seconds'] = round(time.perf_counter()-started,3)
    result = dict(summary=summary, validation=validation, nodes=ui_nodes, edges=ui_edges,
                  clusters=cluster_rows, daily=daily, resilience=robustness,demo=demo,
                  temporal_matches=temporal_matches)
    (out / 'dashboard.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (out / 'validation.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
    demo_text = '# Пятиминутное демо\n\n0:00–0:40 — вопрос: кого проверять первым и почему.\n'
    demo_text += '0:40–1:10 — живой запуск `python analyze.py`; показать три CSV и время.\n'
    demo_text += '1:10–3:40 — открыть в поиске по одному клиенту из списка ниже.\n\n'
    for d in demo:
        demo_text += f"- **{d['gid']} — {d['role']}**: {d['evidence']}\n  Приоритет: {d['priority_evidence']}. Сценарий 1–2 дня: {d['fast_share']:.1%} входа.\n"
    demo_text += '\n3:40–4:30 — показать удаление топ-узлов и сравнение со случайным удалением.\n'
    demo_text += '4:30–5:00 — ограничения, следующий запрос: полный вход seed, продолжение графа за 4-м шагом, точное время и назначение операций.\n'
    demo_text += '\nСценарий FIFO — возможное распределение сумм, не доказанная трассировка тех же денег. Роли — гипотезы.\n'
    (out/'DEMO.md').write_text(demo_text,encoding='utf-8')
    db.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--out', type=Path, default=ROOT / 'out')
    args = parser.parse_args()
    run(args.data, args.out)
