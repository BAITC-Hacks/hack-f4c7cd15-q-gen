"""Read-only SQL analytics over an existing transfer database.

Run: python db_analytics.py --db out/analytics.duckdb --out out/research
Raw transactions stay in the DB; Python receives aggregates and streams CSV rows.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.packages'))
import duckdb


def query(db, sql):
    cur = db.execute(sql)
    columns = [c[0] for c in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def export(db, sql, path):
    cur = db.execute(sql)
    count = 0
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([c[0] for c in cur.description])
        while batch := cur.fetchmany(4096):
            writer.writerows(batch)
            count += len(batch)
    return count


def run(db_path, out):
    db = duckdb.connect(str(db_path), read_only=True)
    try:
        db.execute("SET memory_limit='1GB'")
        # Fail explicitly rather than silently changing totals by dropping bad rows.
        invalid = db.execute('''SELECT count(*) FROM transactions WHERE
          src IS NULL OR dst IS NULL OR date IS NULL OR sum_kzt IS NULL
          OR NOT isfinite(sum_kzt) OR sum_kzt<=0''').fetchone()[0]
        if invalid:
            raise ValueError(f'{invalid} invalid transactions; correct data before analysis')
        summary = query(db, '''SELECT count(*) n_tx, sum(sum_kzt) turnover,
          avg(sum_kzt) mean_amount, median(sum_kzt) median_amount,
          quantile_cont(sum_kzt,0.25) q1, quantile_cont(sum_kzt,0.75) q3,
          quantile_cont(sum_kzt,0.95) p95, max(sum_kzt) max_amount,
          min(date)::VARCHAR date_from,max(date)::VARCHAR date_to,
          count(DISTINCT src) senders,count(DISTINCT dst) recipients
          FROM transactions''')[0]
        if not summary['n_tx']:
            raise ValueError('transactions is empty')
        out.mkdir(parents=True, exist_ok=True)
        daily = query(db, '''SELECT date::VARCHAR AS day,count(*) n_tx,
          sum(sum_kzt) turnover,median(sum_kzt) median_amount
          FROM transactions GROUP BY date ORDER BY date''')
        sender_top = query(db, '''WITH s AS (SELECT src::VARCHAR gid,
          sum(sum_kzt) amount,count(*) n_tx,count(DISTINCT dst) counterparties
          FROM transactions GROUP BY src)
          SELECT *,amount/sum(amount) OVER() AS "share" FROM s
          ORDER BY amount DESC,gid LIMIT 10''')
        recipient_top = query(db, '''WITH s AS (SELECT dst::VARCHAR gid,
          sum(sum_kzt) amount,count(*) n_tx,count(DISTINCT src) counterparties
          FROM transactions GROUP BY dst)
          SELECT *,amount/sum(amount) OVER() AS "share" FROM s
          ORDER BY amount DESC,gid LIMIT 10''')
        # Global exploratory threshold; no labelled fraud data or calibrated probability.
        large_sql = '''WITH bounds AS (SELECT quantile_cont(sum_kzt,0.25) q1,
          quantile_cont(sum_kzt,0.75) q3 FROM transactions)
          SELECT src::VARCHAR src,dst::VARCHAR dst,date,sum_kzt,
          q3+3*(q3-q1) threshold_kzt FROM transactions CROSS JOIN bounds
          WHERE sum_kzt>q3+3*(q3-q1) ORDER BY sum_kzt DESC,src,dst,date'''
        large_count = export(db, large_sql, out / 'large_transfers.csv')
        reciprocal_sql = '''WITH pairs AS (SELECT src,dst,sum(sum_kzt) amount,
          count(*) n_tx FROM transactions GROUP BY src,dst)
          SELECT a.src::VARCHAR gid_a,a.dst::VARCHAR gid_b,
          a.amount a_to_b_kzt,b.amount b_to_a_kzt,a.n_tx a_to_b_tx,b.n_tx b_to_a_tx,
          least(a.amount,b.amount)/greatest(a.amount,b.amount) balance_ratio
          FROM pairs a JOIN pairs b ON a.src=b.dst AND a.dst=b.src
          WHERE a.src<a.dst ORDER BY a.amount+b.amount DESC,a.src,a.dst'''
        reciprocal_count = export(db, reciprocal_sql, out / 'reciprocal_pairs.csv')
        # Amounts received and sent on the same date do not establish money provenance.
        same_day_sql = '''WITH incoming AS (SELECT dst gid,date,sum(sum_kzt) amount,
          count(*) n FROM transactions GROUP BY dst,date),
          outgoing AS (SELECT src gid,date,sum(sum_kzt) amount,count(*) n
          FROM transactions GROUP BY src,date)
          SELECT i.gid::VARCHAR gid,i.date,i.amount in_kzt,o.amount out_kzt,
          i.n in_tx,o.n out_tx,o.amount/i.amount out_in_ratio
          FROM incoming i JOIN outgoing o USING(gid,date)
          WHERE o.amount/i.amount BETWEEN 0.8 AND 1.2
          ORDER BY i.amount+o.amount DESC,i.gid,i.date'''
        same_day_count = export(db, same_day_sql, out / 'same_day_flows.csv')
        # All calendar days in the observed interval, including inactivity, form baseline.
        bursts_sql = '''WITH span AS (SELECT date_diff('day',min(date),max(date))+1 AS n_days
          FROM transactions), day_counts AS (SELECT src,date,count(*) n_tx,
          sum(sum_kzt) amount FROM transactions GROUP BY src,date),
          totals AS (SELECT src,count(*) n_tx FROM transactions GROUP BY src)
          SELECT d.src::VARCHAR gid,d.date,d.n_tx,d.amount,
          t.n_tx::DOUBLE/s.n_days mean_daily_tx,d.n_tx*s.n_days::DOUBLE/t.n_tx multiple
          FROM day_counts d JOIN totals t USING(src) CROSS JOIN span s
          WHERE d.n_tx>=5 AND d.n_tx>3.0*t.n_tx/s.n_days
          ORDER BY multiple DESC,d.n_tx DESC,d.src,d.date'''
        burst_count = export(db, bursts_sql, out / 'activity_bursts.csv')
        report = dict(summary=summary, daily=daily, top_senders=sender_top,
                      top_recipients=recipient_top, signals=dict(large_transfers=large_count,
                      reciprocal_pairs=reciprocal_count,same_day_flows=same_day_count,
                      activity_bursts=burst_count))
        export(db, 'SELECT date,count(*) n_tx,sum(sum_kzt) turnover FROM transactions GROUP BY date ORDER BY date', out/'daily.csv')
        (out/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        money = lambda n: f'{n:,.2f}'.replace(',', ' ')
        peak = max(daily,key=lambda d:d['turnover'])
        top_sender_share = sum(r['share'] for r in sender_top)
        top_recipient_share = sum(r['share'] for r in recipient_top)
        threshold = summary['q3']+3*(summary['q3']-summary['q1'])
        text = f'''# Аналитика банковских переводов

Источник: существующая БД `{db_path.name}`, таблица `transactions`.
Период: {summary['date_from']} — {summary['date_to']}. БД открыта только для чтения.

## Основные результаты

- Переводов: **{summary['n_tx']}**, оборот: **{money(summary['turnover'])} ₸**.
- Активных отправителей: {summary['senders']}; получателей: {summary['recipients']}.
- Средняя сумма: {money(summary['mean_amount'])} ₸; медиана: {money(summary['median_amount'])} ₸.
- 95-й процентиль суммы: {money(summary['p95'])} ₸; максимум: {money(summary['max_amount'])} ₸.
- Максимальный дневной оборот: **{peak['day']}**, {money(peak['turnover'])} ₸, {peak['n_tx']} операций.
- На 10 крупнейших отправителей приходится **{top_sender_share:.1%}** оборота;
  на 10 крупнейших получателей — **{top_recipient_share:.1%}**.

## Сигналы для изучения

1. **{large_count} крупных переводов** выше {money(threshold)} ₸.
   Порог: Q3 + 3 × (Q3 − Q1), рассчитан по всей выборке. Детали: `large_transfers.csv`.
2. **{reciprocal_count} пар со встречными переводами**. Детали: `reciprocal_pairs.csv`.
   Пара учитывается один раз; петли на самого себя исключены. Направления сохранены.
3. **{same_day_count} случаев «клиент-день»** с выходом в пределах 80–120% входа.
   Детали: `same_day_flows.csv`. Это совпадение сумм за день, не доказательство транзита тех же денег.
4. **{burst_count} всплесков «отправитель-день»**: минимум 5 операций и более чем
   тройное среднее число операций за календарный день периода, включая дни без операций.
   Детали: `activity_bursts.csv`. Порог эвристический, сезонность не учитывается.

## Как использовать

Начать проверку с крупных операций и участников с высокой концентрацией оборота.
Сопоставить встречные переводы и совпадения входа/выхода с ролями из `nodes_roles.csv`.
Проверять назначение платежей и полный профиль клиента до каких-либо выводов о причинах.
Сигналы могут пересекаться: их количества нельзя складывать как число подозрительных клиентов.
Отсутствие уникального ID транзакции не позволяет различить дубликат выгрузки и две одинаковые операции;
поэтому одинаковые строки не удаляются автоматически.

## Ограничения

Набор ограничен исходящим обходом на 4 шага, июлем 2026 и суммами от 5 000 ₸.
Входящие seed неполны, дальнейшие операции границы неизвестны. Общий оборот — сумма
переводов, а не уникальный капитал: одни деньги могли пройти несколько рёбер.
Разметки мошенничества нет: сигналы не являются обвинениями или прогнозом риска.
Имеется один месяц наблюдений — устойчивые тренды и сезонность не установлены.

## Исполнение

Python выполняет SQL непосредственно в БД. Сырые транзакции не загружаются целиком
в DataFrame; CSV выгружаются пакетами по 4 096 строк. Итоги и дневные агрегаты загружаются
в Python. Лимит памяти DuckDB — 1 GB; фактическая работа на миллионах строк пока не измерялась.
Это аналитический модуль для DuckDB, не готовый коннектор к любой СУБД.
'''
        (out/'REPORT.md').write_text(text,encoding='utf-8')
        print(json.dumps(report['signals'],ensure_ascii=False))
        print(f'Report: {out / "REPORT.md"}')
        return report
    finally:
        db.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--db',type=Path,default=ROOT/'out/analytics.duckdb')
    ap.add_argument('--out',type=Path,default=ROOT/'out/research')
    args = ap.parse_args()
    run(args.db,args.out)

