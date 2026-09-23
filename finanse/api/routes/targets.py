"""Top priority targets and investigation focus routes."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from api.schemas import TopTargetItem
from core.engine import AMLEngine

router = APIRouter(prefix="/api", tags=["Investigation Targets & Case Studies"])


def get_engine() -> AMLEngine:
    return AMLEngine.get_instance()


@router.get("/top-targets", response_model=List[TopTargetItem], summary="Get Ranked Investigation Targets")
def get_top_targets(
    limit: int = Query(50, ge=1, le=100, description="Number of top targets to return"),
    engine: AMLEngine = Depends(get_engine),
) -> List[TopTargetItem]:
    return engine.get_top_targets()[:limit]


@router.get("/demo-cases", summary="Get 3 Key Demo Cases (Consolidator, Transit, Coordinator)")
def get_demo_cases(engine: AMLEngine = Depends(get_engine)) -> List[Dict[str, Any]]:
    # Dynamic extraction of the 3 primary archetypes
    cases = []
    for role in ("consolidator", "transit", "coordinator"):
        candidates = [n for n in engine.nodes_by_gid.values() if n.role == role]
        if candidates:
            if role == "transit":
                best = max(candidates, key=lambda r: (r.fast_matched_kzt, r.priority_score))
            else:
                best = max(candidates, key=lambda r: r.priority_score)
            cases.append({
                "gid": best.gid,
                "role": best.role,
                "priority_score": best.priority_score,
                "evidence": best.evidence,
                "priority_evidence": best.priority_evidence,
                "fast_share": best.fast_share,
                "turnover_kzt": best.in_kzt + best.out_kzt,
                "in_kzt": best.in_kzt,
                "out_kzt": best.out_kzt,
                "seed_reach": best.seed_reach,
                "neighbor_clusters": best.neighbor_clusters,
            })
    return cases
