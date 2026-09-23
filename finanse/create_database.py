"""Import supplied Parquet into SQLite. Run: python create_database.py."""
import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.packages'))
import duckdb

SCHEMA = '''
CREATE TABLE nodes (
    gid INTEGER PRIMARY KEY,
    depth INTEGER NOT NULL CHECK (depth BETWEEN 0 AND 4),
    is_seed INTEGER NOT NULL CHECK (is_seed IN (0,1))
);
CREATE TABLE edges (
    src INTEGER NOT NULL REFERENCES nodes(gid),
    dst INTEGER NOT NULL REFERENCES nodes(gid),
    amount_tiyn INTEGER NOT NULL CHECK (amount_tiyn > 0),
    sum_kzt REAL GENERATED ALWAYS AS (amount_tiyn / 100.0) VIRTUAL,
    n_tx INTEGER NOT NULL CHECK (n_tx > 0),
    depth INTEGER NOT NULL CHECK (depth BETWEEN 1 AND 4),
    PRIMARY KEY (src,dst)
);
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY,
    src INTEGER NOT NULL REFERENCES nodes(gid),
    dst INTEGER NOT NULL REFERENCES nodes(gid),
    date TEXT NOT NULL CHECK (length(date)=10 AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    amount_tiyn INTEGER NOT NULL CHECK (amount_tiyn > 0),
    sum_kzt REAL GENERATED ALWAYS AS (amount_tiyn / 100.0) VIRTUAL,
    FOREIGN KEY (src,dst) REFERENCES edges(src,dst)
);
CREATE INDEX idx_edges_dst ON edges(dst);
CREATE INDEX idx_transactions_src_date ON transactions(src,date);
CREATE INDEX idx_transactions_dst_date ON transactions(dst,date);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE VIEW daily_turnover AS
SELECT date,count(*) n_tx,sum(amount_tiyn) amount_tiyn,
       sum(amount_tiyn)/100.0 sum_kzt
FROM transactions GROUP BY date;
CREATE VIEW client_turnover AS
WITH incoming AS (
 SELECT dst gid,count(*) in_tx,sum(amount_tiyn) in_tiyn
 FROM transactions GROUP BY dst
), outgoing AS (
 SELECT src gid,count(*) out_tx,sum(amount_tiyn) out_tiyn
 FROM transactions GROUP BY src
)
SELECT n.gid,n.depth,n.is_seed,
 coalesce(i.in_tx,0) in_tx,coalesce(o.out_tx,0) out_tx,
 coalesce(i.in_tiyn,0) in_tiyn,coalesce(o.out_tiyn,0) out_tiyn,
 coalesce(i.in_tiyn,0)/100.0 in_kzt,coalesce(o.out_tiyn,0)/100.0 out_kzt
FROM nodes n LEFT JOIN incoming i ON n.gid=i.gid
LEFT JOIN outgoing o ON n.gid=o.gid;
'''


def tiyn(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def create(data, target):
    # Exclusive creation protects any existing DB from accidental replacement.
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb'):
        pass
    db = None
    reader = None
    try:
        db = sqlite3.connect(target)
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript('BEGIN;\n' + SCHEMA)
        reader = duckdb.connect()
        reader.execute("SET memory_limit='1GB'")
        specs = [
            ('nodes','gid,depth,is_seed','INSERT INTO nodes VALUES (?,?,?)',lambda r:r),
            ('edges','src,dst,sum_kzt,n_tx,depth',
             'INSERT INTO edges(src,dst,amount_tiyn,n_tx,depth) VALUES (?,?,?,?,?)',
             lambda r:(r[0],r[1],tiyn(r[2]),r[3],r[4])),
            ('transactions','src,dst,date,sum_kzt',
             'INSERT INTO transactions(src,dst,date,amount_tiyn) VALUES (?,?,?,?)',
             lambda r:(r[0],r[1],r[2].isoformat(),tiyn(r[3]))),
        ]
        counts = {}
        for table,columns,insert,convert in specs:
            cursor = reader.execute(f'SELECT {columns} FROM read_parquet(?)',[str(data/(table+'.parquet'))])
            count = 0
            while batch := cursor.fetchmany(4096):
                db.executemany(insert,(convert(r) for r in batch))
                count += len(batch)
            counts[table] = count
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key validation failed')
        mismatch = db.execute('''WITH t AS (
          SELECT src,dst,count(*) n,sum(amount_tiyn) amount FROM transactions GROUP BY src,dst)
          SELECT count(*) FROM edges e LEFT JOIN t USING(src,dst)
          WHERE t.src IS NULL OR e.n_tx<>t.n OR e.amount_tiyn<>t.amount''').fetchone()[0]
        if mismatch:
            raise ValueError(f'{mismatch} edge totals differ from transactions')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        db.commit()
        total = db.execute('SELECT sum(amount_tiyn) FROM transactions').fetchone()[0]
        print(f'Database: {target.resolve()}')
        print(f'Rows: {counts}; turnover: {Decimal(total)/100} KZT')
        return counts,total
    except Exception:
        if db:
            db.close()
            db = None
        # This file was exclusively created by this invocation.
        target.unlink(missing_ok=True)
        raise
    finally:
        if reader:
            reader.close()
        if db:
            db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=ROOT/'data')
    parser.add_argument('--db',type=Path,default=ROOT/'database/bank.sqlite3')
    args = parser.parse_args()
    create(args.data,args.db)

