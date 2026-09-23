"""End-to-end synthetic controls: Parquet -> production pipeline -> expectations."""
import json
from pathlib import Path
from analyze import run as analyze, duckdb


def run(destination):
    destination.mkdir(parents=True, exist_ok=True)
    inputs = destination / 'input'
    inputs.mkdir(exist_ok=True)
    nodes, transactions, cases = [], [], []

    def scenario(name, expected, reason, incoming, outgoing, seed=False, depth=1, fast=None):
        gid = 1000 + len(cases)*100
        nodes.append((gid, depth, seed))
        for i, (day, amount) in enumerate(incoming):
            other = gid+i+1
            nodes.append((other, 0, True))
            transactions.append((other,gid,f'2026-07-{day:02d}',amount))
        for i, (day, amount) in enumerate(outgoing):
            other = gid+i+50
            nodes.append((other, 2, False))
            transactions.append((gid,other,f'2026-07-{day:02d}',amount))
        cases.append(dict(name=name,gid=str(gid),expected=expected,reason=reason,expected_fast=fast))

    scenario('Сбор с удержанием','consolidator','4 отправителя; выход составляет 25% входа',[(1,10000)]*4,[(2,10000)])
    scenario('Распределение','distributor','Один вход и шесть разных получателей',[(1,60000)],[(2,10000)]*6)
    scenario('Транзит на следующий день','transit','90% входа выходит на следующий день',[(1,20000)],[(2,18000)],fast=.9)
    scenario('Операции одного дня','peripheral','Порядок внутри дня неизвестен; транзит не подтверждается',[(1,20000)],[(1,18000)],fast=0)
    scenario('Выход через четыре дня','peripheral','Баланс похож на транзит, но окно 1–2 дня нарушено',[(1,20000)],[(5,18000)],fast=0)
    scenario('Неполный вход seed','peripheral','Даже при временном совпадении роль транзита у seed отключена',[(1,20000)],[(2,18000)],seed=True,fast=.9)
    scenario('Обрезанная граница','peripheral','Отсутствие выхода на глубине 4 не означает конечного получателя',[(1,10000)],[],depth=4)
    scenario('Получатель внутри выборки','terminal','Один вход без выхода; не seed и не граница',[(1,10000)],[],depth=2)
    scenario('Изолированный клиент','peripheral','Нет наблюдаемых операций',[],[])
    # Identical bridge topology, differing only in presence of two upstream seeds.
    for center, has_seeds in ((2000, True), (2100, False)):
        nodes.append((center, 2, False))
        groups = [list(range(center+10+k*10, center+15+k*10)) for k in range(3)]
        for k, group in enumerate(groups):
            for i, gid in enumerate(group):
                nodes.append((gid, 1, has_seeds and k<2 and i==0))
            for src in group:
                for dst in group:
                    if src != dst:
                        transactions.append((src,dst,'2026-07-01',100000))
        for src in groups[0][:3]+groups[1][:2]:
            transactions.append((src,center,'2026-07-02',10000))
        for dst in groups[2]:
            transactions.append((center,dst,'2026-07-03',10000))
        cases.append(dict(name='Мост между группами' if has_seeds else 'Такой же мост без seed',
            gid=str(center),expected='coordinator' if has_seeds else 'transit',
            reason='5 входов и 5 выходов; три плотные группы; '+('два upstream seed' if has_seeds else 'нет достижимости от seed — степень сама по себе не даёт coordinator'),
            expected_fast=1,expected_seed=2 if has_seeds else 0))
    with duckdb.connect() as db:
        db.execute('CREATE TABLE nodes(gid BIGINT,depth BIGINT,is_seed BOOLEAN)')
        db.executemany('INSERT INTO nodes VALUES (?,?,?)',nodes)
        db.execute('CREATE TABLE transactions(src BIGINT,dst BIGINT,date DATE,sum_kzt DOUBLE)')
        db.executemany('INSERT INTO transactions VALUES (?,?,?,?)',transactions)
        db.execute('CREATE TABLE edges AS SELECT src,dst,sum(sum_kzt) sum_kzt,count(*) n_tx,1::TINYINT depth FROM transactions GROUP BY src,dst')
        for table in ('nodes','edges','transactions'):
            path=str((inputs/(table+'.parquet')).resolve()).replace("'","''")
            db.execute(f"COPY {table} TO '{path}' (FORMAT PARQUET)")
    result=analyze(inputs,destination/'actual')
    actual={n['gid']:n for n in result['nodes']}
    for case in cases:
        node=actual[case['gid']]
        case.update(actual=node['role'],fast_share=node['fast_share'],evidence=node['evidence'],
                    seed_reach=node['seed_reach'],neighbor_clusters=node['neighbor_clusters'])
        case['passed']=case['actual']==case['expected'] and (case['expected_fast'] is None or abs(case['fast_share']-case['expected_fast'])<1e-9)
        if 'expected_seed' in case:
            case['passed'] = case['passed'] and node['seed_reach']==case['expected_seed'] and node['neighbor_clusters']>=2
    report=dict(passed=sum(c['passed'] for c in cases),total=len(cases),cases=cases,
        limitation='Синтетические контрольные примеры проверяют реализацию правил всех шести ролей, а не точность на реальных клиентах. Пороги выбраны авторами; качество кластеризации на реальных данных и экспертная полезность независимо не оценивались.')
    (destination/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Контрольные сценарии', '', report['limitation'], '',
           '| Сценарий | Ожидаемая роль | Полученная роль | Проверка |','|---|---|---|---|']
    lines += [f"| {c['name']} | {c['expected']} | {c['actual']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in cases]
    lines += ['', 'Каждый сценарий проходит через Parquet, SQL-агрегации, временные признаки и основной классификатор.',
              'Исходные искусственные графы — input/, полный результат — actual/. Они не смешиваются с банковской выборкой.']
    (destination/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if report['passed']!=report['total']:
        raise AssertionError('Control scenarios failed: see report.json')
    return report


if __name__=='__main__':
    report=run(Path(__file__).resolve().parent/'out/control')
    print(f"Controls: {report['passed']}/{report['total']} passed")

