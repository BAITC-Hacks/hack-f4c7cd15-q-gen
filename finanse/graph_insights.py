"""Explainable structural and temporal features; no labels or external data."""
from collections import defaultdict, deque
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
import random
import statistics
import networkx as nx


def cents(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def match_days(events):
    """FIFO allocation of observed incoming amounts to next-day/two-day outgoing.

    Process outgoing before incoming on each day: same-day ordering is unknown.
    Each amount is allocated at most once. This is a scenario, not money provenance.
    """
    queue = deque()
    matches = []
    for day in sorted(events):
        while queue and (day-queue[0][0]).days > 2:
            queue.popleft()
        remaining = events[day]['out']
        while remaining and queue:
            source_day, available = queue[0]
            allocated = min(remaining, available)
            matches.append(dict(in_date=source_day.isoformat(), out_date=day.isoformat(),
                                lag_days=(day-source_day).days, amount_tiyn=allocated))
            remaining -= allocated
            queue[0][1] -= allocated
            if queue[0][1] == 0:
                queue.popleft()
        incoming = events[day]['in']
        if incoming:
            queue.append([day,incoming])
    return matches


def enrich(graph, metrics, membership, tx_rows):
    reach = defaultdict(int)
    for r in metrics:
        if r['is_seed']:
            for gid in nx.single_source_shortest_path_length(graph,r['gid'],cutoff=4):
                if gid != r['gid']:
                    reach[gid] += 1
    events = defaultdict(lambda: defaultdict(lambda: {'in':0,'out':0}))
    for src,dst,day,amount in tx_rows:
        value = cents(amount)
        events[src][day]['out'] += value
        events[dst][day]['in'] += value
    matches = []
    for r in metrics:
        gid = r['gid']
        neighbors = set(graph.predecessors(gid)) | set(graph.successors(gid))
        r['seed_reach'] = reach[gid]
        r['neighbor_clusters'] = len({membership[n] for n in neighbors if membership[n]!=membership[gid]})
        local = match_days(events[gid])
        r['fast_matched_kzt'] = sum(m['amount_tiyn'] for m in local)/100
        incoming = sum(d['in'] for d in events[gid].values())
        r['fast_share'] = sum(m['amount_tiyn'] for m in local)/incoming if incoming else 0.0
        r['fast_windows'] = len(local)
        for m in local:
            matches.append(dict(gid=str(gid),**m))
    return matches


def assign_priority(metrics):
    maxima = {
        'turnover':max(r['in_kzt']+r['out_kzt'] for r in metrics),
        'degree':max(r['in_deg']+r['out_deg'] for r in metrics),
        'seed':max(r['seed_reach'] for r in metrics),
        'bridge':max(r['neighbor_clusters'] for r in metrics),
    }
    weights = dict(turnover=.25,degree=.20,seed=.20,bridge=.15,fast=.10,cycle=.10)
    for r in metrics:
        values = dict(turnover=r['in_kzt']+r['out_kzt'],degree=r['in_deg']+r['out_deg'],
                      seed=r['seed_reach'],bridge=r['neighbor_clusters'])
        components = {key: weights[key]*math.log1p(value)/math.log1p(maxima[key])
                      if maxima[key] else 0.0 for key,value in values.items()}
        components['fast'] = .10*r['fast_share'] if not r['is_seed'] and not r['truncated_by_depth'] else 0.0
        components['cycle'] = .10*int(r['cycle_member'])
        for key,value in components.items():
            r['priority_'+key] = value
        r['priority_score'] = round(sum(components.values()),6)
        r['priority_evidence'] = (
            f"Оборот {values['turnover']:.0f} (+{components['turnover']:.3f}); "
            f"связей {values['degree']} (+{components['degree']:.3f}); "
            f"seed {r['seed_reach']} (+{components['seed']:.3f}); "
            f"внешних групп {r['neighbor_clusters']} (+{components['bridge']:.3f}); "
            f"1–2д {r['fast_share']:.0%} (+{components['fast']:.3f}); цикл +{components['cycle']:.2f}")


def resilience(graph, ranked):
    """Weak connectivity after removal, compared with equal-sized random removal."""
    ug = graph.to_undirected()
    gids = sorted(ug)
    baseline = max(map(len,nx.connected_components(ug)),default=0)
    rng = random.Random(42)
    result = []
    for count in (1,5,10):
        if count>=len(gids):
            continue
        removed = [r['gid'] for r in ranked[:count]]
        after = ug.subgraph(set(gids)-set(removed))
        components = list(nx.connected_components(after))
        largest = max(map(len,components),default=0)
        random_largest = []
        for _ in range(30):
            random_removed = set(rng.sample(gids,count))
            random_largest.append(max(map(len,nx.connected_components(ug.subgraph(set(gids)-random_removed))),default=0))
        result.append(dict(removed_count=count,removed_gids=[str(g) for g in removed],
            baseline_largest=baseline,remaining_nodes=len(after),largest_component=largest,
            components=len(components),isolates=nx.number_of_isolates(after),
            random_largest_median=statistics.median(random_largest),
            random_largest_min=min(random_largest),random_largest_max=max(random_largest),
            random_trials=30))
    return result


def cluster_description(group,members,edges):
    internal = [e for e in edges if e['src'] in group and e['dst'] in group]
    source = defaultdict(float)
    target = defaultdict(float)
    internal_amount = sum(e['sum_kzt'] for e in internal)
    for e in internal:
        source[e['src']] += e['sum_kzt']
        target[e['dst']] += e['sum_kzt']
    cross = sum(e['sum_kzt'] for e in edges if (e['src'] in group)!=(e['dst'] in group))
    source_share = max(source.values(),default=0)/internal_amount if internal_amount else 0
    target_share = max(target.values(),default=0)/internal_amount if internal_amount else 0
    internal_share = internal_amount/(internal_amount+cross) if internal_amount+cross else 0
    if internal_amount==cross==0:
        hypothesis = 'Изолированный клиент; наблюдаемых переводов нет'
    else:
        shape = 'распределение от ведущего отправителя' if source_share>=.5 else (
            'сбор у ведущего получателя' if target_share>=.5 else 'смешанная сеть переводов')
        hypothesis = (f"Гипотеза: {shape}; {len(group)} узлов; "
                      f"top-отправитель {source_share:.0%}, top-получатель {target_share:.0%} внутреннего оборота; "
                      f"внутренние переводы {internal_share:.0%} от связанных с группой; "
                      f"seed={sum(r['is_seed'] for r in members)}. Назначение неизвестно.")
    return dict(hypothesis=hypothesis,internal_share=internal_share,
                top_sender_share=source_share,top_recipient_share=target_share,cross_kzt=cross)
