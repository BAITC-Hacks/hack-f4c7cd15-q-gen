import tempfile
import unittest
from pathlib import Path
from db_analytics import duckdb, run


class DatabaseAnalyticsTests(unittest.TestCase):
    def test_known_flows_and_read_only_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/'source.duckdb'
            db = duckdb.connect(str(path))
            db.execute('CREATE TABLE transactions(src BIGINT,dst BIGINT,date DATE,sum_kzt DOUBLE)')
            db.execute("INSERT INTO transactions VALUES (1,2,'2026-07-01',100),(2,1,'2026-07-01',100),(3,4,'2026-07-02',10000)")
            db.close()
            before = path.read_bytes()
            report = run(path,root/'reports')
            self.assertEqual(report['summary']['turnover'],10200)
            self.assertEqual(sum(d['turnover'] for d in report['daily']),10200)
            self.assertEqual(report['signals']['reciprocal_pairs'],1)
            self.assertEqual(report['signals']['same_day_flows'],2)
            self.assertEqual(report['signals']['activity_bursts'],0)
            self.assertAlmostEqual(sum(r['share'] for r in report['top_senders']),1)
            self.assertEqual(before,path.read_bytes())


if __name__ == '__main__':
    unittest.main()

