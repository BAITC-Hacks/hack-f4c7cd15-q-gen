"""Independent output checks against the original transaction totals."""
import csv
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.packages'))
import duckdb
from analyze import classify


class AnalyticsTests(unittest.TestCase):
    def test_outputs_and_conservation(self):
        data = json.loads((ROOT / 'out/dashboard.json').read_text(encoding='utf-8'))
        db = duckdb.connect()
        total, count = db.execute('SELECT sum(sum_kzt),count(*) FROM read_parquet(?)', [str(ROOT/'data/transactions.parquet')]).fetchone()
        self.assertEqual(data['summary']['transactions'], count)
        self.assertAlmostEqual(data['summary']['total_kzt'], total, places=2)
        self.assertAlmostEqual(sum(n['in_kzt'] for n in data['nodes']), total, places=2)
        self.assertAlmostEqual(sum(n['out_kzt'] for n in data['nodes']), total, places=2)
        self.assertAlmostEqual(sum(n['pagerank'] for n in data['nodes']), 1.0, places=8)
        expected = {str(r[0]) for r in db.execute('SELECT gid FROM read_parquet(?)',[str(ROOT/'data/nodes.parquet')]).fetchall()}
        self.assertEqual({n['gid'] for n in data['nodes']}, expected)
        self.assertTrue(all(isinstance(n['gid'], str) for n in data['nodes']))
        self.assertEqual(sum(c['n_nodes'] for c in data['clusters']),len(expected))
        for n in data['nodes']:
            self.assertTrue(0 <= n['priority_score'] <= 1)
            self.assertTrue(0 <= n['role_score'] <= 1)
            self.assertTrue(n['evidence'] and len(n['evidence']) <= 200)
            if n['truncated_by_depth']:
                self.assertNotEqual(n['role'], 'terminal')
        with (ROOT/'out/top_nodes.csv').open(encoding='utf-8-sig', newline='') as f:
            top = list(csv.DictReader(f))
        self.assertGreaterEqual(len(top),20)
        scores = [float(r['priority_score']) for r in top]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertTrue(all(v==0 for v in data['validation'].values()))

    def test_sampling_boundaries(self):
        r=dict(in_deg=1,out_deg=0,in_kzt=10000,out_kzt=0,is_seed=False,truncated_by_depth=True,pass_through=0)
        self.assertEqual(classify(r)[0], 'peripheral')
        r.update(truncated_by_depth=False)
        self.assertEqual(classify(r)[0], 'terminal')
        r.update(is_seed=True,out_deg=1,pass_through=1)
        self.assertNotEqual(classify(r)[0], 'transit')


if __name__ == '__main__':
    unittest.main()

