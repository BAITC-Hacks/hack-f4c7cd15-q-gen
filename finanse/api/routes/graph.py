"""Graph data and ego-network visualization routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from api.schemas import GraphData
from core.engine import AMLEngine

router = APIRouter(prefix="/api/graph", tags=["Graph Visualization & Ego Networks"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("", response_model=GraphData, summary="Get Filtered Graph for Canvas Rendering")
def get_graph(
    min_priority: float = Query(0.0, ge=0.0, le=1.0, description="Minimum priority score filter"),
    role: Optional[str] = Query(None, description="Filter nodes by role"),
    cluster_id: Optional[int] = Query(None, description="Filter nodes by cluster ID"),
    limit_nodes: int = Query(500, ge=10, le=2500, description="Max nodes to return for visual performance"),
    engine: AMLEngine = Depends(get_engine),
) -> GraphData:
    return engine.get_graph_data(
        min_priority=min_priority,
        role=role,
        cluster_id=cluster_id,
        limit_nodes=limit_nodes,
    )


@router.get("/subgraph/{gid}", response_model=GraphData, summary="Get Ego-Network Subgraph Around a GID")
def get_subgraph(
    gid: str,
    depth: int = Query(1, ge=1, le=2, description="Neighborhood depth (1 or 2 hops)"),
    engine: AMLEngine = Depends(get_engine),
) -> GraphData:
    data = engine.get_ego_subgraph(gid=gid, depth=depth)
    if not data:
        raise HTTPException(status_code=404, detail=f"Client with GID '{gid}' not found in graph.")
    return data
