import unittest
from weekly_analytics import summarize,compare


class WeeklyTests(unittest.TestCase):
    def test_partial_week_normalization(self):
        r=summarize([('1','2','2026-07-01',500),('1','2','2026-07-06',700)],'2026-07-01','2026-07-12')
        c=compare(r,'2026-06-29','2026-07-06')
        self.assertEqual(c['before']['days'],5)
        self.assertTrue(c['before']['partial'])
        self.assertEqual(c['amount']['delta'],0)
        self.assertEqual(compare(r,'2026-06-29','2026-07-06','total')['amount']['delta'],200)

    def test_zero_baseline_peers_and_ids(self):
        gid='100000000000000001'
        r=summarize([(gid,'2','2026-07-01',100),('3','2','2026-07-07',200)],'2026-07-01','2026-07-12')
        c=compare(r,'2026-06-29','2026-07-06','total')
        rows={n['gid']:n for n in c['clients']}
        self.assertIsNone(rows['3']['amount']['pct'])
        self.assertEqual(rows['3']['amount']['status'],'appeared')
        self.assertEqual(rows[gid]['amount']['pct'],-100)
        self.assertEqual(rows['2']['new_peers'],1)
        self.assertEqual(rows['2']['lost_peers'],1)

    def test_self_transfer_and_empty_week(self):
        r=summarize([('1','1','2026-07-01',5.01)],'2026-07-01','2026-07-12')
        a=r['weeks'][0];n=a['clients']['1']
        self.assertEqual(a['amount_tiyn'],501)
        self.assertEqual(n['amount_tiyn'],501)
        self.assertEqual(n['n_tx'],1)
        self.assertEqual(n['peers'],[])
        self.assertEqual(r['weeks'][1]['n_tx'],0)

    def test_invalid_comparison(self):
        r=summarize([],'2026-07-01','2026-07-12')
        for args in [('2026-07-06','2026-06-29'),('2026-06-29','2026-06-29'),('bad','2026-07-06')]:
            with self.assertRaises(ValueError):compare(r,*args)


if __name__=='__main__':unittest.main()
