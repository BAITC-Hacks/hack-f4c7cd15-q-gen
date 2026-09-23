"""One command: raw data -> analytical outputs -> contract check -> optional UI."""
import argparse
import json
import time
from pathlib import Path
from analyze import run as analyze
from db_analytics import run as research
from validate_outputs import validate

ROOT=Path(__file__).resolve().parent


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true',help='Start local dashboard after computation')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    start=time.perf_counter()
    if not (ROOT/'database/bank.sqlite3').exists():
        from create_database import create
        create(ROOT/'data', ROOT/'database/bank.sqlite3')
    analyze(ROOT/'data',ROOT/'out')
    research(ROOT/'out/analytics.duckdb',ROOT/'out/research')
    checks=validate(ROOT/'data',ROOT/'out')
    from control_scenarios import run as controls
    control_report=controls(ROOT/'out/control')
    checks['control_scenarios_passed']=control_report['passed']
    checks['full_pipeline_seconds']=round(time.perf_counter()-start,3)
    (ROOT/'out/run_validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks))
    if args.serve:
        import uvicorn
        print(f'Starting MoneyGraph AML Intelligence API & Dashboard on http://127.0.0.1:{args.port}', flush=True)
        print(f'Interactive Swagger Docs: http://127.0.0.1:{args.port}/docs', flush=True)
        print(f'Interactive Dashboard UI: http://127.0.0.1:{args.port}/analytics', flush=True)
        uvicorn.run("api.app:app", host="0.0.0.0", port=args.port)

