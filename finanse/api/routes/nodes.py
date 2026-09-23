"""Nodes intelligence and search routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from api.schemas import PaginatedNodesResponse, NodeDossier, TransferItem, TransactionItem
from core.engine import AMLEngine

router = APIRouter(prefix="/api/nodes", tags=["Nodes & Investigation Dossiers"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("", response_model=PaginatedNodesResponse, summary="Search and Filter Nodes")
def list_nodes(
    query: Optional[str] = Query(None, description="Search by gid prefix or substring"),
    role: Optional[str] = Query(None, description="Filter by role: coordinator, consolidator, transit, distributor, terminal, peripheral"),
    cluster_id: Optional[int] = Query(None, description="Filter by Louvain cluster ID"),
    is_seed: Optional[bool] = Query(None, description="Filter by seed status (initial 81 couriers)"),
    min_priority: Optional[float] = Query(None, description="Minimum priority score (0.0 to 1.0)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("priority_score", description="Sort field: priority_score, turnover, in_deg, out_deg, in_kzt, out_kzt, pagerank, fast_share"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    engine: AMLEngine = Depends(get_engine),
) -> PaginatedNodesResponse:
    return engine.search_nodes(
        query=query,
        role=role,
        cluster_id=cluster_id,
        is_seed=is_seed,
        min_priority=min_priority,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )


@router.get("/{gid}", response_model=NodeDossier, summary="Get Full Node Intelligence Dossier")
def get_node(gid: str, engine: AMLEngine = Depends(get_engine)) -> NodeDossier:
    dossier = engine.get_node_dossier(gid)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Client with GID '{gid}' not found in graph.")
    return dossier


@router.get("/{gid}/counterparties", response_model=List[TransferItem], summary="Get Node Counterparties")
def get_node_counterparties(
    gid: str,
    direction: Optional[str] = Query(None, pattern="^(in|out)$", description="Filter by direction"),
    engine: AMLEngine = Depends(get_engine),
) -> List[TransferItem]:
    dossier = engine.get_node_dossier(gid)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Client with GID '{gid}' not found.")

    res = []
    if not direction or direction == "in":
        res.extend(dossier.incoming_transfers)
    if not direction or direction == "out":
        res.extend(dossier.outgoing_transfers)
    return res


@router.get("/{gid}/transactions", response_model=List[TransactionItem], summary="Get Node Transaction History")
def get_node_transactions(gid: str, engine: AMLEngine = Depends(get_engine)) -> List[TransactionItem]:
    dossier = engine.get_node_dossier(gid)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Client with GID '{gid}' not found.")
    return dossier.recent_transactions
