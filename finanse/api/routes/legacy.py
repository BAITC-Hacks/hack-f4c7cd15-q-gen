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
