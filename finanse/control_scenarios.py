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
        case.update(actual=node['role'],fast_share=node['fast_share'],evidence=node['evidence'])
        case['passed']=case['actual']==case['expected'] and (case['expected_fast'] is None or abs(case['fast_share']-case['expected_fast'])<1e-9)
    report=dict(passed=sum(c['passed'] for c in cases),total=len(cases),cases=cases,
        limitation='Синтетические контрольные примеры проверяют реализацию правил, а не точность ролей на реальных клиентах. Пороги выбраны авторами; координатор и качество кластеризации этим набором не оцениваются.')
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

