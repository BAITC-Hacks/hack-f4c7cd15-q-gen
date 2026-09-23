"""Shortest chronological transfer chain, using observed transactions only."""
from collections import defaultdict, deque
from datetime import date
import sqlite3


def find_chain(rows, source, target, max_hops=4, max_gap=2, start=None, end=None,
               state_limit=50000):
    if source == target:
        raise ValueError('Выберите двух разных клиентов')
    if not 1 <= max_hops <= 8 or not 1 <= max_gap <= 31:
        raise ValueError('Допустимо 1–8 переводов и 1–31 день между ними')
    first = date.fromisoformat(start) if start else date.min
    last = date.fromisoformat(end) if end else date.max
    if first > last:
        raise ValueError('Начало периода позже окончания')
    adjacent = defaultdict(list)
    for src, dst, day, amount in rows:
        day = date.fromisoformat(str(day))
        if first <= day <= last:
            adjacent[str(src)].append((str(dst), day, int(amount)))
    for edges in adjacent.values():
        edges.sort(key=lambda x: (x[1], x[0], -x[2]))
    queue = deque([(source, None, [])])
    visited = set()
    states = 0
    while queue:
        node, previous, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        for dst, day, amount in adjacent[node]:
            if previous is not None and not 1 <= (day-previous).days <= max_gap:
                continue
            key = (dst, day)
            if key in visited:
                continue
            if states >= state_limit:
                return {'status': 'limited', 'steps': [], 'states': states}
            visited.add(key)
            states += 1
            step = {'src': node, 'dst': dst, 'date': day.isoformat(),
                    'amount_tiyn': amount}
            chain = path + [step]
            if dst == target:
                return {'status': 'found', 'steps': chain, 'states': states,
                        'bottleneck_tiyn': min(x['amount_tiyn'] for x in chain)}
            queue.append((dst, day, chain))
    return {'status': 'not_found', 'steps': [], 'states': states}


def query_chain(db_path, params):
    source, target = params.get('source', ''), params.get('target', '')
    if not source.isdecimal() or not target.isdecimal() or max(len(source), len(target)) > 19:
        raise ValueError('Укажите корректные gid отправителя и получателя')
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        for gid in (source, target):
            if not db.execute('SELECT 1 FROM nodes WHERE CAST(gid AS TEXT)=?', (gid,)).fetchone():
                raise ValueError(f'Клиент {gid} отсутствует в выборке')
        rows = db.execute('SELECT src,dst,date,amount_tiyn FROM transactions').fetchall()
    return find_chain(rows, source, target, int(params.get('hops', 4)),
                      int(params.get('gap', 2)), params.get('start'), params.get('end'))


def example_chain(db_path):
    """Pick a reproducible two-operation example, without fixed client IDs."""
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('''SELECT a.src,b.dst FROM transactions a
          JOIN transactions b ON a.dst=b.src
          WHERE julianday(b.date)-julianday(a.date) BETWEEN 1 AND 2
          AND a.src<>b.dst AND a.src<>a.dst AND b.src<>b.dst
          AND NOT EXISTS (SELECT 1 FROM transactions c WHERE c.src=a.src AND c.dst=b.dst)
          ORDER BY MIN(a.amount_tiyn,b.amount_tiyn) DESC,a.src,b.dst LIMIT 1''').fetchone()
    return {'source': str(row[0]), 'target': str(row[1])} if row else {}
