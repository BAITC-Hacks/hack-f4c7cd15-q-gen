"""Create a reproducible source/data delivery without environments or secrets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
files = [root/name for name in (
    'README.md', 'LOCAL_QA.md', 'run_api.py', 'test_api.py', 'package_project.py', 'requirements.txt', '.gitignore', 'analyze.py', 'create_database.py',
    'db_analytics.py', 'serve.py', 'dashboard.html', 'database_queries.sql',
    'test_analysis.py', 'test_db_analytics.py','test_graph_insights.py','graph_insights.py',
    'validate_outputs.py','run.py','dashboard.js','architecture.svg',
    'home.html','home.js','styles.css','routes.html','routes.js',
    'route_search.py','test_route_search.py','control_scenarios.py','CASE_STUDY.md','review_export.py','test_review_export.py','weekly_analytics.py','test_weekly_analytics.py','weekly.html','weekly.js','client_report.py','test_client_report.py','recurring_patterns.py','test_recurring_patterns.py','patterns.html','patterns.js','preferences.js','themes.css') if (root/name).exists()]
if (root.parent/'REPORT_RAMAZAN.md').exists():
    files.append(root.parent/'REPORT_RAMAZAN.md')
if (root.parent/'.gitignore').exists():
    files.append(root.parent/'.gitignore')
allowed = {'.parquet', '.sqlite3', '.duckdb', '.csv', '.json', '.md', '.py', '.txt'}
for folder in ('data', 'database', 'out', 'starter', 'api', 'core'):
    files.extend(p for p in (root/folder).rglob('*')
                 if p.is_file() and p.suffix in allowed and '__pycache__' not in p.parts)
destination = root.parent/'finanse.zip' if (root.parent/'README.md').exists() else root/'finanse.zip'
with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        if path.exists():
            archive_name = 'finanse/' + (path.relative_to(root).as_posix() if root in path.parents else path.name)
            archive.write(path, archive_name)
with ZipFile(destination) as archive:
    assert archive.testzip() is None
print(f'{len(files)} files; {destination.stat().st_size} bytes; ZIP integrity OK')
