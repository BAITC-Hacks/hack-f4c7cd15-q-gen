import unittest
from recurring_patterns import detect


class RecurringTests(unittest.TestCase):
    def test_two_chronological_occurrences(self):
        rows=[('1','2','2026-07-01',100),('2','3','2026-07-02',90),
              ('1','2','2026-07-10',200),('2','3','2026-07-12',180)]
        r=detect(rows)
        self.assertEqual(r['count'],1)
        self.assertEqual(r['patterns'][0]['occurrences'],2)

    def test_same_day_duplicates_do_not_create_repeat(self):
        rows=[('1','2','2026-07-01',100)]*5+[('2','3','2026-07-02',50)]*4
        self.assertEqual(detect(rows)['count'],0)

    def test_output_day_not_reused(self):
        rows=[('1','2','2026-07-01',100),('1','2','2026-07-02',100),('2','3','2026-07-03',200)]
        self.assertEqual(detect(rows)['count'],0)

    def test_direction_same_day_window_and_cycles(self):
        for target,days in [('3',(1,10)),('3',(4,13)),('1',(2,11))]:
            rows=[('1','2','2026-07-01',100),('1','2','2026-07-10',100),
                  ('2',target,f'2026-07-{days[0]:02d}',100),('2',target,f'2026-07-{days[1]:02d}',100)]
            self.assertEqual(detect(rows)['count'],0)


if __name__=='__main__':unittest.main()
