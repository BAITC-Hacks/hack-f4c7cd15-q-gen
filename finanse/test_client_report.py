import unittest
from pathlib import Path
from client_report import load_report,html_report,pdf_report


class ClientReportTests(unittest.TestCase):
    def test_report_matches_snapshot_and_escapes(self):
        r=load_report(Path(__file__).resolve().parent,'100000007629096100')
        self.assertEqual(r['node']['in_kzt'],1075170)
        self.assertEqual(len(r['edges']),5)
        self.assertEqual(len(r['weekly']),5)
        r['node']['evidence']='<script>alert(1)</script>'
        html=html_report(r)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn(r['gid'],html)

    def test_reject_unknown_or_invalid_gid(self):
        for gid in ('../README.md','abc','1',''):
            with self.assertRaises(ValueError):load_report(Path(__file__).resolve().parent,gid)


if __name__=='__main__':unittest.main()
