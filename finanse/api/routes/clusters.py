"""Clusters and Louvain community intelligence routes."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from api.schemas import ClusterItem
from core.engine import AMLEngine

router = APIRouter(prefix="/api/clusters", tags=["Clusters & Communities"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("", response_model=List[ClusterItem], summary="List All Louvain Communities")
def list_clusters(engine: AMLEngine = Depends(get_engine)) -> List[ClusterItem]:
    return engine.get_clusters_list()


@router.get("/{cluster_id}", summary="Get Cluster Detailed Structure and Members")
def get_cluster(cluster_id: int, engine: AMLEngine = Depends(get_engine)) -> Dict[str, Any]:
    details = engine.get_cluster_details(cluster_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Cluster with ID {cluster_id} not found.")
    return details
