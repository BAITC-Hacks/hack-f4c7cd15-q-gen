"""Routes package for MoneyGraph AML Intelligence API."""
from api.routes.overview import router as overview_router
from api.routes.nodes import router as nodes_router
from api.routes.graph import router as graph_router
from api.routes.clusters import router as clusters_router
from api.routes.targets import router as targets_router
from api.routes.trace import router as trace_router
from api.routes.legacy import router as legacy_router
from api.routes.copilot import router as copilot_router

__all__ = [
    "overview_router",
    "nodes_router",
    "graph_router",
    "clusters_router",
    "targets_router",
    "trace_router",
    "legacy_router",
    "copilot_router",
]
