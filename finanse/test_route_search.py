import unittest
from route_search import find_chain


class RoutesTest(unittest.TestCase):
    def test_chronology_and_exact_amount(self):
        rows = [('1','2','2026-07-02',9001), ('2','3','2026-07-01',8000),
                ('2','3','2026-07-02',7000), ('2','3','2026-07-04',6001)]
        result = find_chain(rows, '1', '3')
        self.assertEqual([x['date'] for x in result['steps']], ['2026-07-02','2026-07-04'])
        self.assertEqual(result['bottleneck_tiyn'], 6001)

    def test_later_arrival_must_be_preserved(self):
        rows = [('1','2','2026-07-01',100),('1','2','2026-07-10',100),
                ('2','3','2026-07-11',100)]
        self.assertEqual(find_chain(rows,'1','3')['steps'][0]['date'], '2026-07-10')

    def test_shortest_limits_and_date_filter(self):
        rows = [('1','2','2026-07-01',100),('2','3','2026-07-02',100),
                ('1','3','2026-07-20',100)]
        self.assertEqual(len(find_chain(rows,'1','3')['steps']),1)
        self.assertEqual(find_chain(rows,'1','3',max_hops=1,end='2026-07-10')['status'],'not_found')
        self.assertEqual(find_chain(rows,'1','3',state_limit=0)['status'],'limited')

    def test_direction_gap_and_invalid_input(self):
        rows = [('1','2','2026-07-01',100),('2','3','2026-07-10',100)]
        self.assertEqual(find_chain(rows,'1','3')['status'],'not_found')
        self.assertEqual(find_chain(rows,'3','1')['status'],'not_found')
        with self.assertRaises(ValueError): find_chain(rows,'1','1')
        with self.assertRaises(ValueError): find_chain(rows,'1','3',max_hops=9)


if __name__ == '__main__': unittest.main()

