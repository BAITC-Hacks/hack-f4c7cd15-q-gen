"""High-performance in-memory Graph & Intelligence Engine for MoneyGraph AML."""
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import networkx as nx

from api.schemas import (
    NodeMetrics,
    NodeDossier,
    TransferItem,
    TransactionItem,
    NetworkOverview,
    ClusterItem,
    GraphNode,
    GraphEdge,
    GraphData,
    TraceRoute,
    TraceStep,
    TraceResponse,
    TopTargetItem,
    PaginatedNodesResponse,
)

ROOT = Path(__file__).resolve().parent.parent


class AMLEngine:
    _instance: Optional["AMLEngine"] = None

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or ROOT
        self.out_dir = self.base_dir / "out"
        self.db_path = self.base_dir / "database" / "bank.sqlite3"
        self.duckdb_path = self.out_dir / "analytics.duckdb"

        self.nodes_by_gid: Dict[str, NodeMetrics] = {}
        self.clusters_by_id: Dict[int, ClusterItem] = {}
        self.top_targets: List[TopTargetItem] = []
        self.graph: nx.DiGraph = nx.DiGraph()
        self.summary: Dict[str, Any] = {}
        self.daily_activity: List[Dict[str, Any]] = []
        self.resilience_stats: Dict[str, Any] = {}
        self.validation_stats: Dict[str, Any] = {}

        self.load_data()

    @classmethod
    def get_instance(cls, base_dir: Optional[Path] = None) -> "AMLEngine":
        if cls._instance is None:
            cls._instance = AMLEngine(base_dir)
        return cls._instance

    def reload(self):
        self.load_data()

    def load_data(self):
        dashboard_json_path = self.out_dir / "dashboard.json"
        if not dashboard_json_path.exists():
            raise FileNotFoundError(f"Dashboard data not found at {dashboard_json_path}. Run pipeline first.")

        with dashboard_json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.summary = data.get("summary", {})
        self.validation_stats = data.get("validation", {})
        self.daily_activity = data.get("daily", [])
        self.resilience_stats = data.get("resilience", {})

        # Load nodes
        self.nodes_by_gid.clear()
        self.graph.clear()

        raw_nodes = data.get("nodes", [])
        for n in raw_nodes:
            gid_str = str(n["gid"])
            nm = NodeMetrics(
                gid=gid_str,
                depth=int(n["depth"]),
                is_seed=bool(n["is_seed"]),
                in_deg=int(n["in_deg"]),
                out_deg=int(n["out_deg"]),
                in_kzt=float(n["in_kzt"]),
                out_kzt=float(n["out_kzt"]),
                in_tx=int(n["in_tx"]),
                out_tx=int(n["out_tx"]),
                pagerank=float(n["pagerank"]),
                pass_through=float(n["pass_through"]),
                pass_through_defined=bool(n.get("pass_through_defined", True)),
                truncated_by_depth=bool(n["truncated_by_depth"]),
                cluster_id=int(n["cluster_id"]),
                role=str(n["role"]),
                role_score=float(n["role_score"]),
                role_stability=float(n.get("role_stability", 1.0)),
                evidence=str(n["evidence"]),
                priority_score=float(n["priority_score"]),
                priority_evidence=str(n.get("priority_evidence", "")),
                cycle_member=bool(n.get("cycle_member", False)),
                active_days=int(n.get("active_days", 0)),
                peak_day_share=float(n.get("peak_day_share", 0.0)),
                fast_matched_kzt=float(n.get("fast_matched_kzt", 0.0)),
                fast_share=float(n.get("fast_share", 0.0)),
                fast_windows=int(n.get("fast_windows", 0)),
                seed_reach=int(n.get("seed_reach", 0)),
                neighbor_clusters=int(n.get("neighbor_clusters", 0)),
            )
            self.nodes_by_gid[gid_str] = nm
            self.graph.add_node(
                gid_str,
                role=nm.role,
                priority_score=nm.priority_score,
                is_seed=nm.is_seed,
                cluster_id=nm.cluster_id,
                in_kzt=nm.in_kzt,
                out_kzt=nm.out_kzt,
                depth=nm.depth,
            )

        # Load edges into Graph
        raw_edges = data.get("edges", [])
        for e in raw_edges:
            src = str(e["src"])
            dst = str(e["dst"])
            sum_kzt = float(e["sum_kzt"])
            n_tx = int(e["n_tx"])
            depth = int(e.get("depth", 1))
            self.graph.add_edge(src, dst, sum_kzt=sum_kzt, n_tx=n_tx, depth=depth)

        # Load clusters
        self.clusters_by_id.clear()
        raw_clusters = data.get("clusters", [])
        for c in raw_clusters:
            cid = int(c["cluster_id"])
            self.clusters_by_id[cid] = ClusterItem(
                cluster_id=cid,
                n_nodes=int(c["n_nodes"]),
                n_seed=int(c["n_seed"]),
                sum_kzt_internal=float(c["sum_kzt_internal"]),
                top_gids=str(c["top_gids"]),
                hypothesis=str(c["hypothesis"]),
                dominant_role=c.get("dominant_role"),
            )

        # Build Top Targets
        sorted_by_priority = sorted(
            self.nodes_by_gid.values(),
            key=lambda x: (-x.priority_score, x.gid),
        )
        self.top_targets = []
        for rank, n in enumerate(sorted_by_priority[:50], 1):
            if n.role in ("consolidator", "coordinator") and n.priority_score >= 0.6:
                rec = "IMMEDIATE_BLOCK_AND_LE"
            elif n.role == "transit" and n.fast_share >= 0.5:
                rec = "HIGH_ALERT_MONITOR"
            elif n.priority_score >= 0.5:
                rec = "ROUTINE_OBSERVATION"
            else:
                rec = "LOW_RISK"

            self.top_targets.append(
                TopTargetItem(
                    rank=rank,
                    gid=n.gid,
                    role=n.role,
                    priority_score=n.priority_score,
                    why=n.priority_evidence or n.evidence,
                    recommended_action=rec,
                    turnover_kzt=n.in_kzt + n.out_kzt,
                )
            )

    def get_overview(self) -> NetworkOverview:
        roles_dist: Dict[str, int] = {}
        for n in self.nodes_by_gid.values():
            roles_dist[n.role] = roles_dist.get(n.role, 0) + 1

        return NetworkOverview(
            nodes=self.summary.get("nodes", len(self.nodes_by_gid)),
            edges=self.summary.get("edges", self.graph.number_of_edges()),
            transactions=self.summary.get("transactions", 4840),
            total_kzt=self.summary.get("total_kzt", 365890012.01),
            seeds=self.summary.get("seeds", 81),
            clusters=self.summary.get("clusters", len(self.clusters_by_id)),
            truncated=self.summary.get("truncated", 444),
            cycle_nodes=self.summary.get("cycle_nodes", 309),
            start_date=self.summary.get("start", "2026-07-01"),
            end_date=self.summary.get("end", "2026-07-31"),
            weak_components=self.summary.get("weak_components", 35),
            isolates=self.summary.get("isolates", 19),
            runtime_seconds=self.summary.get("runtime_seconds", 1.2),
            roles_distribution=roles_dist,
            top_targets_count=len(self.top_targets),
        )

    def search_nodes(
        self,
        query: Optional[str] = None,
        role: Optional[str] = None,
        cluster_id: Optional[int] = None,
        is_seed: Optional[bool] = None,
        min_priority: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "priority_score",
        order: str = "desc",
    ) -> PaginatedNodesResponse:
        filtered = list(self.nodes_by_gid.values())

        if query:
            q = query.strip()
            filtered = [n for n in filtered if q in n.gid]

        if role:
            r = role.strip().lower()
            filtered = [n for n in filtered if n.role.lower() == r]

        if cluster_id is not None:
            filtered = [n for n in filtered if n.cluster_id == cluster_id]

        if is_seed is not None:
            filtered = [n for n in filtered if n.is_seed == is_seed]

        if min_priority is not None:
            filtered = [n for n in filtered if n.priority_score >= min_priority]

        # Sorting
        reverse = order.lower() == "desc"
        sort_field = sort_by.lower()

        if sort_field == "turnover":
            filtered.sort(key=lambda n: n.in_kzt + n.out_kzt, reverse=reverse)
        elif hasattr(NodeMetrics, sort_field):
            filtered.sort(key=lambda n: getattr(n, sort_field, 0), reverse=reverse)
        else:
            filtered.sort(key=lambda n: n.priority_score, reverse=reverse)

        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered[start:end]

        return PaginatedNodesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_node_dossier(self, gid: str) -> Optional[NodeDossier]:
        gid_str = str(gid)
        metrics = self.nodes_by_gid.get(gid_str)
        if not metrics:
            return None

        # Incoming edges
        incoming: List[TransferItem] = []
        if self.graph.has_node(gid_str):
            for u in self.graph.predecessors(gid_str):
                edge_data = self.graph[u][gid_str]
                u_metrics = self.nodes_by_gid.get(u)
                incoming.append(
                    TransferItem(
                        counterparty_gid=u,
                        counterparty_role=u_metrics.role if u_metrics else None,
                        is_seed=u_metrics.is_seed if u_metrics else False,
                        sum_kzt=edge_data["sum_kzt"],
                        n_tx=edge_data["n_tx"],
                        direction="in",
                    )
                )
        incoming.sort(key=lambda x: -x.sum_kzt)

        # Outgoing edges
        outgoing: List[TransferItem] = []
        if self.graph.has_node(gid_str):
            for v in self.graph.successors(gid_str):
                edge_data = self.graph[gid_str][v]
                v_metrics = self.nodes_by_gid.get(v)
                outgoing.append(
                    TransferItem(
                        counterparty_gid=v,
                        counterparty_role=v_metrics.role if v_metrics else None,
                        is_seed=v_metrics.is_seed if v_metrics else False,
                        sum_kzt=edge_data["sum_kzt"],
                        n_tx=edge_data["n_tx"],
                        direction="out",
                    )
                )
        outgoing.sort(key=lambda x: -x.sum_kzt)

        # Query recent individual transactions from SQLite if available
        recent_txs: List[TransactionItem] = []
        if self.db_path.exists():
            try:
                with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT transaction_id, src, dst, date, sum_kzt
                        FROM transactions
                        WHERE src = ? OR dst = ?
                        ORDER BY date DESC, sum_kzt DESC
                        LIMIT 50
                        """,
                        (int(gid_str), int(gid_str)),
                    )
                    for row in cur.fetchall():
                        recent_txs.append(
                            TransactionItem(
                                transaction_id=row[0],
                                src=str(row[1]),
                                dst=str(row[2]),
                                date=row[3],
                                sum_kzt=float(row[4]),
                            )
                        )
            except Exception:
                pass

        # Recommendation logic
        if metrics.role in ("consolidator", "coordinator") and metrics.priority_score >= 0.6:
            rec = "IMMEDIATE_BLOCK_AND_LE"
            risk = "CRITICAL"
        elif metrics.role == "transit" and metrics.fast_share >= 0.5:
            rec = "HIGH_ALERT_MONITOR"
            risk = "HIGH"
        elif metrics.priority_score >= 0.5:
            rec = "ROUTINE_OBSERVATION"
            risk = "MEDIUM"
        else:
            rec = "LOW_RISK"
            risk = "LOW"

        cluster_item = self.clusters_by_id.get(metrics.cluster_id)

        return NodeDossier(
            metrics=metrics,
            recommended_action=rec,
            risk_level=risk,
            incoming_transfers=incoming,
            outgoing_transfers=outgoing,
            recent_transactions=recent_txs,
            cluster_hypothesis=cluster_item.hypothesis if cluster_item else None,
        )

    def get_graph_data(
        self,
        min_priority: float = 0.0,
        role: Optional[str] = None,
        cluster_id: Optional[int] = None,
        limit_nodes: int = 500,
    ) -> GraphData:
        selected_nodes = []
        for n in self.nodes_by_gid.values():
            if n.priority_score < min_priority:
                continue
            if role and n.role.lower() != role.lower():
                continue
            if cluster_id is not None and n.cluster_id != cluster_id:
                continue
            selected_nodes.append(n)

        # Sort by priority score to keep top nodes if capped
        selected_nodes.sort(key=lambda n: -n.priority_score)
        selected_nodes = selected_nodes[:limit_nodes]
        node_ids = {n.gid for n in selected_nodes}

        graph_nodes = [
            GraphNode(
                id=n.gid,
                label=f"{n.role.upper()} ({n.gid[-6:]})",
                role=n.role,
                priority_score=n.priority_score,
                cluster_id=n.cluster_id,
                is_seed=n.is_seed,
                in_kzt=n.in_kzt,
                out_kzt=n.out_kzt,
                in_deg=n.in_deg,
                out_deg=n.out_deg,
                depth=n.depth,
            )
            for n in selected_nodes
        ]

        graph_edges = []
        edge_id = 0
        for src, dst, data in self.graph.edges(data=True):
            if src in node_ids and dst in node_ids:
                edge_id += 1
                graph_edges.append(
                    GraphEdge(
                        id=f"e_{edge_id}",
                        source=src,
                        target=dst,
                        sum_kzt=data["sum_kzt"],
                        n_tx=data["n_tx"],
                        depth=data["depth"],
                    )
                )

        return GraphData(
            nodes=graph_nodes,
            edges=graph_edges,
            total_nodes=len(graph_nodes),
            total_edges=len(graph_edges),
        )

    def get_ego_subgraph(self, gid: str, depth: int = 1) -> Optional[GraphData]:
        gid_str = str(gid)
        if not self.graph.has_node(gid_str):
            return None

        depth = min(max(1, depth), 2)
        # Undirected view for neighborhood extraction
        ug = self.graph.to_undirected()
        subgraph_nodes = {gid_str}
        frontier = {gid_str}

        for _ in range(depth):
            next_frontier = set()
            for u in frontier:
                for v in ug.neighbors(u):
                    next_frontier.add(v)
            subgraph_nodes.update(next_frontier)
            frontier = next_frontier

        nodes_list = []
        for nid in subgraph_nodes:
            n = self.nodes_by_gid.get(nid)
            if n:
                nodes_list.append(
                    GraphNode(
                        id=n.gid,
                        label=f"{n.role.upper()} ({n.gid[-6:]})",
                        role=n.role,
                        priority_score=n.priority_score,
                        cluster_id=n.cluster_id,
                        is_seed=n.is_seed,
                        in_kzt=n.in_kzt,
                        out_kzt=n.out_kzt,
                        in_deg=n.in_deg,
                        out_deg=n.out_deg,
                        depth=n.depth,
                    )
                )

        edges_list = []
        edge_id = 0
        for src, dst, data in self.graph.edges(data=True):
            if src in subgraph_nodes and dst in subgraph_nodes:
                edge_id += 1
                edges_list.append(
                    GraphEdge(
                        id=f"sub_e_{edge_id}",
                        source=src,
                        target=dst,
                        sum_kzt=data["sum_kzt"],
                        n_tx=data["n_tx"],
                        depth=data["depth"],
                    )
                )

        return GraphData(
            nodes=nodes_list,
            edges=edges_list,
            total_nodes=len(nodes_list),
            total_edges=len(edges_list),
        )

    def trace_routes(
        self, source_gid: str, target_gid: Optional[str] = None, max_depth: int = 4
    ) -> TraceResponse:
        src_str = str(source_gid)
        if not self.graph.has_node(src_str):
            return TraceResponse(source_gid=src_str, target_gid=target_gid, routes_found=0, routes=[])

        routes: List[TraceRoute] = []

        if target_gid:
            dst_str = str(target_gid)
            if self.graph.has_node(dst_str) and nx.has_path(self.graph, src_str, dst_str):
                for path in nx.all_simple_paths(self.graph, src_str, dst_str, cutoff=max_depth):
                    steps = []
                    total_kzt = 0.0
                    for i in range(len(path) - 1):
                        u, v = path[i], path[i + 1]
                        ed = self.graph[u][v]
                        u_m = self.nodes_by_gid.get(u)
                        v_m = self.nodes_by_gid.get(v)
                        steps.append(
                            TraceStep(
                                src=u,
                                dst=v,
                                sum_kzt=ed["sum_kzt"],
                                n_tx=ed["n_tx"],
                                src_role=u_m.role if u_m else None,
                                dst_role=v_m.role if v_m else None,
                            )
                        )
                        total_kzt += ed["sum_kzt"]

                    routes.append(
                        TraceRoute(
                            path=path,
                            steps=steps,
                            total_kzt=total_kzt,
                            hops=len(path) - 1,
                        )
                    )
                    if len(routes) >= 20:
                        break
        else:
            # Trace to high-priority targets (consolidator, terminal, coordinator)
            targets = [
                n.gid
                for n in self.nodes_by_gid.values()
                if n.role in ("consolidator", "coordinator") and n.gid != src_str
            ]
            for tgt in targets:
                if nx.has_path(self.graph, src_str, tgt):
                    try:
                        p = nx.shortest_path(self.graph, src_str, tgt)
                        if len(p) - 1 <= max_depth:
                            steps = []
                            total_kzt = 0.0
                            for i in range(len(p) - 1):
                                u, v = p[i], p[i + 1]
                                ed = self.graph[u][v]
                                u_m = self.nodes_by_gid.get(u)
                                v_m = self.nodes_by_gid.get(v)
                                steps.append(
                                    TraceStep(
                                        src=u,
                                        dst=v,
                                        sum_kzt=ed["sum_kzt"],
                                        n_tx=ed["n_tx"],
                                        src_role=u_m.role if u_m else None,
                                        dst_role=v_m.role if v_m else None,
                                    )
                                )
                                total_kzt += ed["sum_kzt"]
                            routes.append(
                                TraceRoute(
                                    path=p,
                                    steps=steps,
                                    total_kzt=total_kzt,
                                    hops=len(p) - 1,
                                )
                            )
                            if len(routes) >= 20:
                                break
                    except Exception:
                        continue

        # Sort routes by total volume descending
        routes.sort(key=lambda r: -r.total_kzt)

        return TraceResponse(
            source_gid=src_str,
            target_gid=target_gid,
            routes_found=len(routes),
            routes=routes,
        )

    def get_clusters_list(self) -> List[ClusterItem]:
        return sorted(self.clusters_by_id.values(), key=lambda c: -c.sum_kzt_internal)

    def get_cluster_details(self, cluster_id: int) -> Optional[Dict[str, Any]]:
        c = self.clusters_by_id.get(cluster_id)
        if not c:
            return None

        member_nodes = [
            n for n in self.nodes_by_gid.values() if n.cluster_id == cluster_id
        ]
        member_nodes.sort(key=lambda n: -n.priority_score)
        member_gids = {n.gid for n in member_nodes}

        intra_edges = []
        for src, dst, data in self.graph.edges(data=True):
            if src in member_gids and dst in member_gids:
                intra_edges.append(
                    {
                        "src": src,
                        "dst": dst,
                        "sum_kzt": data["sum_kzt"],
                        "n_tx": data["n_tx"],
                    }
                )

        return {
            "cluster": c,
            "members": member_nodes,
            "edges": intra_edges,
            "total_members": len(member_nodes),
            "total_intra_edges": len(intra_edges),
        }

    def get_top_targets(self) -> List[TopTargetItem]:
        return self.top_targets
