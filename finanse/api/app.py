"""FastAPI Application factory for MoneyGraph AML Intelligence."""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import (
    overview_router,
    nodes_router,
    graph_router,
    clusters_router,
    targets_router,
    trace_router,
    legacy_router,
    copilot_router,
)
from core.engine import AMLEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload the AML graph engine on startup
    engine = AMLEngine.get_instance()
    print(f"AML Graph Engine loaded: {len(engine.nodes_by_gid)} nodes, {engine.graph.number_of_edges()} edges.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="MoneyGraph AML Intelligence API",
        description=(
            "Высокопроизводительный аналитический бэкенд финансовой разведки и расследования "
            "транзакционных графов в рамках хакатона. Позволяет мгновенно классифицировать роли "
            "(coordinator, consolidator, distributor, transit, terminal, peripheral), ранжировать цели, "
            "извлекать эго-сети, строить трассировку потоков и предоставлять данные для любого фронтенда."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Enable CORS for any frontend origin (React, Vite, Next.js, Vue, mobile apps)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Performance monitoring header
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time-Ms"] = f"{process_time * 1000:.2f}"
        return response

    # Include all modular routers
    app.include_router(overview_router)
    app.include_router(nodes_router)
    app.include_router(graph_router)
    app.include_router(clusters_router)
    app.include_router(targets_router)
    app.include_router(trace_router)
    app.include_router(legacy_router)
    app.include_router(copilot_router)

    return app


app = create_app()
