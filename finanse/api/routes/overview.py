"""Overview and health routes."""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from api.schemas import NetworkOverview
from core.engine import AMLEngine

router = APIRouter(prefix="/api", tags=["Overview & Health"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("/health", summary="System Health Check")
def health_check(engine: AMLEngine = Depends(get_engine)) -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "MoneyGraph AML Intelligence Backend",
        "version": "1.0.0",
        "nodes_loaded": len(engine.nodes_by_gid),
        "edges_loaded": engine.graph.number_of_edges(),
        "database_connected": engine.db_path.exists(),
        "duckdb_connected": engine.duckdb_path.exists(),
    }


@router.get("/stats", response_model=NetworkOverview, summary="Network High-Level Statistics")
def get_stats(engine: AMLEngine = Depends(get_engine)) -> NetworkOverview:
    return engine.get_overview()


@router.get("/daily", summary="Daily Turnover and Transaction Count")
def get_daily_activity(engine: AMLEngine = Depends(get_engine)) -> List[Dict[str, Any]]:
    return engine.daily_activity


@router.get("/resilience", summary="Network Resilience & Target Removal Analysis")
def get_resilience(engine: AMLEngine = Depends(get_engine)) -> Dict[str, Any]:
    return engine.resilience_stats


@router.get("/validation", summary="Data Integrity and Quality Checks")
def get_validation(engine: AMLEngine = Depends(get_engine)) -> Dict[str, Any]:
    return engine.validation_stats
