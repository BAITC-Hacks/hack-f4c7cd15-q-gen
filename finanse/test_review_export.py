import csv
import io
import unittest
from review_export import export_review


class ReviewExportTests(unittest.TestCase):
    def test_selection_order_precision_and_reasons(self):
        def node(gid,priority,seed=False,boundary=False):
            return dict(gid=gid,priority_score=priority,role='peripheral',role_score=.2,
                role_stability=1,evidence='Вход 10, выход 0',priority_evidence='Оборот +0.2',
                in_kzt=10,out_kzt=0,seed_reach=0,is_seed=seed,truncated_by_depth=boundary)
        a='100000000000000001';b='100000000000000002'
        data={'nodes':[node(a,.2,seed=True),node(b,.8,boundary=True)]}
        rows=list(csv.DictReader(io.StringIO(export_review(data,[a,b,a]).lstrip('\ufeff'))))
        self.assertEqual([r['gid'] for r in rows],[b,a])
        self.assertIn('4-м',rows[0]['next_data_request'])
        self.assertIn('seed',rows[1]['next_data_request'])
        self.assertEqual(rows[1]['evidence'],'Вход 10, выход 0')

    def test_invalid_selection(self):
        for ids in ([],['unknown'],[str(i) for i in range(51)]):
            with self.assertRaises(ValueError):export_review({'nodes':[]},ids)


if __name__=='__main__':unittest.main()

