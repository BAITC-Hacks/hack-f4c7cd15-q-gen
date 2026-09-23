"""Pydantic schemas for MoneyGraph AML Intelligence REST API."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TransferItem(BaseModel):
    counterparty_gid: str
    counterparty_role: Optional[str] = None
    is_seed: bool = False
    sum_kzt: float
    n_tx: int
    direction: str = Field(description="'in' or 'out'")


class TransactionItem(BaseModel):
    transaction_id: Optional[int] = None
    src: str
    dst: str
    date: str
    sum_kzt: float


class NodeMetrics(BaseModel):
    gid: str
    depth: int
    is_seed: bool
    in_deg: int
    out_deg: int
    in_kzt: float
    out_kzt: float
    in_tx: int
    out_tx: int
    pagerank: float
    pass_through: float
    pass_through_defined: bool = True
    truncated_by_depth: bool
    cluster_id: int
    role: str
    role_score: float
    role_stability: float
    evidence: str
    priority_score: float
    priority_evidence: str
    cycle_member: bool
    active_days: int
    peak_day_share: float
    fast_matched_kzt: float
    fast_share: float
    fast_windows: int
    seed_reach: int
    neighbor_clusters: int


class NodeDossier(BaseModel):
    metrics: NodeMetrics
    recommended_action: str = Field(
        description="'IMMEDIATE_BLOCK_AND_LE' | 'HIGH_ALERT_MONITOR' | 'ROUTINE_OBSERVATION' | 'LOW_RISK'"
    )
    risk_level: str = Field(description="'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'")
    incoming_transfers: List[TransferItem]
    outgoing_transfers: List[TransferItem]
    recent_transactions: List[TransactionItem]
    cluster_hypothesis: Optional[str] = None


class PaginatedNodesResponse(BaseModel):
    items: List[NodeMetrics]
    total: int
    page: int
    page_size: int
    total_pages: int


class NetworkOverview(BaseModel):
    nodes: int
    edges: int
    transactions: int
    total_kzt: float
    seeds: int
    clusters: int
    truncated: int
    cycle_nodes: int
    start_date: str
    end_date: str
    weak_components: int
    isolates: int
    runtime_seconds: float
    roles_distribution: Dict[str, int]
    top_targets_count: int


class ClusterItem(BaseModel):
    cluster_id: int
    n_nodes: int
    n_seed: int
    sum_kzt_internal: float
    top_gids: str
    hypothesis: str
    dominant_role: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    label: str
    role: str
    priority_score: float
    cluster_id: int
    is_seed: bool
    in_kzt: float
    out_kzt: float
    in_deg: int
    out_deg: int
    depth: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    sum_kzt: float
    n_tx: int
    depth: int


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int


class TraceStep(BaseModel):
    src: str
    dst: str
    sum_kzt: float
    n_tx: int
    src_role: Optional[str] = None
    dst_role: Optional[str] = None


class TraceRoute(BaseModel):
    path: List[str]
    steps: List[TraceStep]
    total_kzt: float
    hops: int


class TraceResponse(BaseModel):
    source_gid: str
    target_gid: Optional[str] = None
    routes_found: int
    routes: List[TraceRoute]


class TopTargetItem(BaseModel):
    rank: int
    gid: str
    role: str
    priority_score: float
    why: str
    recommended_action: str
    turnover_kzt: float
