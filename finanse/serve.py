"""Serve only the dashboard and named reports, on localhost."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
from urllib.parse import urlsplit, parse_qs
from route_search import query_chain, example_chain
from review_export import export_review
from weekly_analytics import compare
from client_report import load_report, html_report, pdf_report

ROOT = Path(__file__).resolve().parent
ROUTES = {'/': ('home.html', 'text/html; charset=utf-8'),
          '/analytics': ('dashboard.html', 'text/html; charset=utf-8'),
          '/routes': ('routes.html', 'text/html; charset=utf-8'),
          '/weekly': ('weekly.html', 'text/html; charset=utf-8'),
          '/weekly.js': ('weekly.js', 'text/javascript; charset=utf-8'),
          '/patterns': ('patterns.html', 'text/html; charset=utf-8'),
          '/patterns.js': ('patterns.js', 'text/javascript; charset=utf-8'),
          '/preferences.js': ('preferences.js', 'text/javascript; charset=utf-8'),
          '/themes.css': ('themes.css', 'text/css; charset=utf-8'),
          '/api/patterns': ('out/patterns.json', 'application/json; charset=utf-8'),
          '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
          '/home.js': ('home.js', 'text/javascript; charset=utf-8'),
          '/routes.js': ('routes.js', 'text/javascript; charset=utf-8'),
          '/dashboard.js': ('dashboard.js', 'text/javascript; charset=utf-8'),
          '/copilot': ('copilot.html', 'text/html; charset=utf-8'),
          '/copilot.js': ('copilot.js', 'text/javascript; charset=utf-8'),
          '/api/analytics': ('out/dashboard.json', 'application/json; charset=utf-8')}
for name in ('nodes_roles', 'clusters', 'top_nodes'):
    ROUTES['/download/' + name + '.csv'] = ('out/' + name + '.csv', 'text/csv; charset=utf-8')
ROUTES['/download/temporal_matches.csv'] = ('out/temporal_matches.csv','text/csv; charset=utf-8')
ROUTES['/demo'] = ('out/DEMO.md','text/plain; charset=utf-8')
ROUTES['/api/controls'] = ('out/control/report.json','application/json; charset=utf-8')
ROUTES['/controls-report'] = ('out/control/REPORT.md','text/plain; charset=utf-8')
ROUTES['/case-study'] = ('CASE_STUDY.md','text/plain; charset=utf-8')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path in ('/report','/download/client.pdf'):
            params=parse_qs(urlsplit(self.path).query)
            try:
                report=load_report(ROOT,params.get('gid',[''])[0])
                pdf=urlsplit(self.path).path.endswith('.pdf')
                payload=pdf_report(report) if pdf else html_report(report).encode('utf-8')
            except ValueError:
                self.send_error(400,'Unknown or invalid client');return
            except (OSError,RuntimeError,ImportError) as error:
                payload=('Отчёт недоступен. '+str(error)).encode('utf-8')
                self.send_response(503);self.send_header('Content-Type','text/plain; charset=utf-8')
                self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
            self.send_response(200)
            self.send_header('Content-Type','application/pdf' if pdf else 'text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store')
            if pdf:self.send_header('Content-Disposition','attachment; filename="client-'+report['gid']+'.pdf"')
            self.end_headers();self.wfile.write(payload);return
        if urlsplit(self.path).path == '/api/weekly':
            try:
                report=json.loads((ROOT/'out/weekly.json').read_text(encoding='utf-8'))
                params={k:v[0] for k,v in parse_qs(urlsplit(self.path).query).items()}
                if 'before' in params or 'after' in params:
                    result=compare(report,params.get('before'),params.get('after'),params.get('mode','daily'))
                else:
                    result={'weeks':[{k:v for k,v in w.items() if k!='clients'} for w in report['weeks']]}
                status=200
            except ValueError as error:
                result,status={'error':str(error)},400
            except OSError:
                result,status={'error':'Выполните python weekly_analytics.py для подготовки недельных данных'},503
            payload=json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(payload)
            return
        if urlsplit(self.path).path == '/download/review.csv':
            try:
                params=parse_qs(urlsplit(self.path).query)
                analytics=json.loads((ROOT/'out/dashboard.json').read_text(encoding='utf-8'))
                payload=export_review(analytics,params.get('gid',[])).encode('utf-8')
            except ValueError as error:
                self.send_error(400, 'Invalid selection')
                return
            except OSError:
                self.send_error(503, 'Run python run.py first')
                return
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="review.csv"')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(payload)
            return
        if urlsplit(self.path).path in ('/api/routes', '/api/route-example'):
            try:
                params = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                result = (example_chain(ROOT / 'database/bank.sqlite3')
                          if urlsplit(self.path).path == '/api/route-example'
                          else query_chain(ROOT / 'database/bank.sqlite3', params))
                status = 200
            except (ValueError, OverflowError) as error:
                result, status = {'error': str(error)}, 400
            except Exception:
                result, status = {'error': 'База недоступна. Проверьте database/bank.sqlite3.'}, 503
            payload = json.dumps(result, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)
            return
        route = ROUTES.get(self.path.split('?')[0])
        if not route:
            self.send_error(404)
            return
        path, mime = route
        try:
            data = (ROOT / path).read_bytes()
        except FileNotFoundError:
            self.send_error(503, 'Run python analyze.py first')
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        if self.path.startswith('/download/'):
            self.send_header('Content-Disposition', 'attachment; filename="' + Path(path).name + '"')
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    print(f'Open http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
