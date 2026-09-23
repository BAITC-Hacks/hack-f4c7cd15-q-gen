"""Backward compatibility and static routes."""
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from route_search import query_chain, example_chain
from review_export import export_review

ROOT = Path(__file__).resolve().parent.parent.parent
router = APIRouter(tags=["Legacy & Compatibility"])


@router.get("/api/analytics", summary="Get Raw Dashboard Analytics JSON")
def get_raw_analytics():
    path = ROOT / "out" / "dashboard.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Dashboard analytics not found. Run python run.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/routes", summary="Query Chronological Transfer Chain")
def get_routes(
    source: str = Query(..., description="Source gid"),
    target: str = Query(..., description="Target gid"),
    hops: int = Query(4, ge=1, le=8),
    gap: int = Query(2, ge=1, le=31),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    db_path = ROOT / "database" / "bank.sqlite3"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="SQLite database not found.")
    try:
        params = {"source": source, "target": target, "hops": str(hops), "gap": str(gap)}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return query_chain(db_path, params)
    except (ValueError, OverflowError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/route-example", summary="Pick a Reproducible Transfer Chain Example")
def get_route_example():
    db_path = ROOT / "database" / "bank.sqlite3"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="SQLite database not found.")
    try:
        return example_chain(db_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/review.csv", summary="Download Analyst Review CSV")
def download_review(gid: List[str] = Query(...)):
    analytics_path = ROOT / "out" / "dashboard.json"
    if not analytics_path.exists():
        raise HTTPException(status_code=503, detail="Run python run.py first.")
    try:
        analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
        payload = export_review(analytics, gid).encode("utf-8")
        return Response(
            content=payload,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="review.csv"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/controls", summary="Synthetic Control Scenario Report")
def get_controls():
    path = ROOT / "out" / "control" / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Control report not found.")
    return json.loads(path.read_text(encoding="utf-8"))


# Static HTML/JS/CSS routes
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_home():
    path = ROOT / "home.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/analytics", response_class=HTMLResponse, include_in_schema=False)
def serve_analytics():
    path = ROOT / "dashboard.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/routes", response_class=HTMLResponse, include_in_schema=False)
def serve_routes():
    path = ROOT / "routes.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/styles.css", include_in_schema=False)
def serve_css():
    return FileResponse(str(ROOT / "styles.css"), media_type="text/css; charset=utf-8")


@router.get("/home.js", include_in_schema=False)
def serve_home_js():
    return FileResponse(str(ROOT / "home.js"), media_type="text/javascript; charset=utf-8")


@router.get("/routes.js", include_in_schema=False)
def serve_routes_js():
    return FileResponse(str(ROOT / "routes.js"), media_type="text/javascript; charset=utf-8")


@router.get("/dashboard.js", include_in_schema=False)
def serve_dashboard_js():
    return FileResponse(str(ROOT / "dashboard.js"), media_type="text/javascript; charset=utf-8")


@router.get("/demo", response_class=PlainTextResponse, include_in_schema=False)
def serve_demo():
    path = ROOT / "out" / "DEMO.md"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/case-study", response_class=PlainTextResponse, include_in_schema=False)
def serve_case_study():
    path = ROOT / "CASE_STUDY.md"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/controls-report", response_class=PlainTextResponse, include_in_schema=False)
def serve_controls_report():
    path = ROOT / "out" / "control" / "REPORT.md"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# Additional local analytics, shared with the standalone dashboard.
from client_report import load_report, html_report, pdf_report
from weekly_analytics import compare

@router.get('/api/weekly')
def weekly(before: Optional[str] = None, after: Optional[str] = None, mode: str = 'daily'):
    try:
        report=json.loads((ROOT/'out/weekly.json').read_text(encoding='utf-8'))
        if before is not None or after is not None:
            return compare(report,before,after,mode)
        return {'weeks':[{k:v for k,v in w.items() if k!='clients'} for w in report['weeks']]}
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))
    except OSError:
        raise HTTPException(status_code=503,detail='Run python run.py first')

@router.get('/report',response_class=HTMLResponse)
def client_html(gid: str):
    try:
        return HTMLResponse(html_report(load_report(ROOT,gid)))
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))

@router.get('/download/client.pdf')
def client_pdf(gid: str):
    try:
        data=pdf_report(load_report(ROOT,gid))
        return Response(data,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="client-{gid}.pdf"'})
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))

# Named assets only; paths cannot be supplied by the caller.
def add_asset(url,relative,media):
    def asset():
        return FileResponse(str(ROOT/relative),media_type=media)
    router.add_api_route(url,asset,methods=['GET'],include_in_schema=False)

for url,relative,media in [
    ('/weekly','weekly.html','text/html'),('/patterns','patterns.html','text/html'),
    ('/weekly.js','weekly.js','text/javascript'),('/patterns.js','patterns.js','text/javascript'),
    ('/preferences.js','preferences.js','text/javascript'),('/themes.css','themes.css','text/css'),
    ('/api/patterns','out/patterns.json','application/json')]:
    add_asset(url,relative,media)

@router.get("/download/{filename}", summary="Download Export File")
def download_file(filename: str):
    allowed_files = {
        "nodes_roles.csv": ROOT / "out" / "nodes_roles.csv",
        "clusters.csv": ROOT / "out" / "clusters.csv",
        "top_nodes.csv": ROOT / "out" / "top_nodes.csv",
        "temporal_matches.csv": ROOT / "out" / "temporal_matches.csv",
        "bank.sqlite3": ROOT / "database" / "bank.sqlite3",
    }
    target = allowed_files.get(filename)
    if not target or not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    media_type = "application/octet-stream"
    if filename.endswith(".csv"):
        media_type = "text/csv; charset=utf-8"

    return FileResponse(
        path=str(target),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# Integrated graph frontend assets (explicit allowlist).
for url, (relative, media) in {'/graph': ('graph.html', 'text/html; charset=utf-8'), '/legacy-styles.css': ('legacy-styles.css', 'text/css; charset=utf-8'), '/ui/analytics.js': ('ui/analytics.js', 'text/javascript; charset=utf-8'), '/ui/card.js': ('ui/card.js', 'text/javascript; charset=utf-8'), '/ui/controls.js': ('ui/controls.js', 'text/javascript; charset=utf-8'), '/ui/data.js': ('ui/data.js', 'text/javascript; charset=utf-8'), '/ui/geometry.js': ('ui/geometry.js', 'text/javascript; charset=utf-8'), '/ui/graph.js': ('ui/graph.js', 'text/javascript; charset=utf-8'), '/ui/layout-core.js': ('ui/layout-core.js', 'text/javascript; charset=utf-8'), '/ui/layout-worker.js': ('ui/layout-worker.js', 'text/javascript; charset=utf-8'), '/ui/layout.js': ('ui/layout.js', 'text/javascript; charset=utf-8'), '/ui/legend.js': ('ui/legend.js', 'text/javascript; charset=utf-8'), '/ui/overview.js': ('ui/overview.js', 'text/javascript; charset=utf-8'), '/ui/routes-shell.js': ('ui/routes-shell.js', 'text/javascript; charset=utf-8'), '/ui/scene2d.js': ('ui/scene2d.js', 'text/javascript; charset=utf-8'), '/ui/scene3d.js': ('ui/scene3d.js', 'text/javascript; charset=utf-8'), '/ui/shell.js': ('ui/shell.js', 'text/javascript; charset=utf-8'), '/ui/state.js': ('ui/state.js', 'text/javascript; charset=utf-8'), '/ui/theme.css': ('ui/theme.css', 'text/css; charset=utf-8'), '/vendor/OrbitControls.js': ('vendor/OrbitControls.js', 'text/javascript; charset=utf-8'), '/vendor/three.core.js': ('vendor/three.core.js', 'text/javascript; charset=utf-8'), '/vendor/three.module.js': ('vendor/three.module.js', 'text/javascript; charset=utf-8')}.items():
    add_asset(url, relative, media)

add_asset("/copilot", "copilot.html", "text/html")
add_asset("/copilot.js", "copilot.js", "text/javascript")
