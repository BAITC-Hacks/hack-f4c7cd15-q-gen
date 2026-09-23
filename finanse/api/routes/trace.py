"""Money tracing and path route search."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from api.schemas import TraceResponse
from core.engine import AMLEngine

router = APIRouter(prefix="/api/trace", tags=["Money Tracing & Flow Paths"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("", response_model=TraceResponse, summary="Trace Money Paths From Source to Target")
def trace_money(
    source_gid: str = Query(..., description="Source client GID (e.g. seed courier or intermediate mule)"),
    target_gid: Optional[str] = Query(None, description="Target client GID (optional: if omitted, traces to top consolidators/coordinators)"),
    max_hops: int = Query(4, ge=1, le=6, description="Max traversal depth"),
    engine: AMLEngine = Depends(get_engine),
) -> TraceResponse:
    return engine.trace_routes(source_gid=source_gid, target_gid=target_gid, max_depth=max_hops)
