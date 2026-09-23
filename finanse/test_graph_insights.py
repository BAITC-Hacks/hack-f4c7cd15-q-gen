import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'.packages'))
from datetime import date
import unittest
import networkx as nx
from graph_insights import match_days,resilience,assign_priority
from validate_outputs import validate
from analyze import classify


class InsightTests(unittest.TestCase):
    def test_time_order_and_no_double_spending(self):
        events={date(2026,7,1):{'in':10000,'out':5000},
                date(2026,7,2):{'in':0,'out':6000},
                date(2026,7,3):{'in':0,'out':6000},
                date(2026,7,4):{'in':0,'out':10000}}
        matches=match_days(events)
        self.assertEqual([m['amount_tiyn'] for m in matches],[6000,4000])
        self.assertEqual([m['lag_days'] for m in matches],[1,2])

    def test_same_day_and_expired_receipts_excluded(self):
        events={date(2026,7,1):{'in':10000,'out':10000},date(2026,7,4):{'in':0,'out':10000}}
        self.assertEqual(match_days(events),[])

    def test_bridge_removal(self):
        g=nx.DiGraph([(0,1),(0,2),(0,3),(0,4)])
        r=resilience(g,[{'gid':i} for i in range(5)])[0]
        self.assertEqual(r['baseline_largest'],5)
        self.assertEqual(r['largest_component'],1)
        self.assertEqual(r['isolates'],4)
        self.assertGreater(r['random_largest_median'],r['largest_component'])

    def test_priority_breakdown_and_seed_exclusion(self):
        r=dict(in_kzt=100,out_kzt=100,in_deg=1,out_deg=1,seed_reach=2,
               neighbor_clusters=1,fast_share=1,is_seed=True,truncated_by_depth=False,cycle_member=True)
        assign_priority([r])
        self.assertEqual(r['priority_fast'],0)
        self.assertAlmostEqual(r['priority_score'],.9)

    def test_submission_contract(self):
        root=Path(__file__).resolve().parent
        checks=validate(root/'data',root/'out')
        self.assertEqual(checks['nodes'],2248)
        self.assertGreaterEqual(checks['top_nodes'],20)

    def test_collection_requires_observed_retention(self):
        r=dict(in_deg=6,out_deg=1,in_kzt=100,out_kzt=800,pass_through=8,
               is_seed=False,truncated_by_depth=False,fast_share=1)
        self.assertNotEqual(classify(r)[0],'consolidator')
        r.update(out_kzt=30,pass_through=.3)
        self.assertEqual(classify(r)[0],'consolidator')


if __name__=='__main__':
    unittest.main()
