import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings

from tracegraph.agent.mcp_server import build_mcp_server
from tracegraph.api.routes import admin, graph_views, investigator, ops, scoreboard, tasks
from tracegraph.api.state import AppState
from tracegraph.api.task_runs import TaskRegistry
from tracegraph.config import Settings, get_settings
from tracegraph.graph.connection import GraphDatabase, GraphUnavailableError
from tracegraph.llm.embeddings import Embedder, LocalEmbedder
from tracegraph.llm.factory import ModelFactory


# Everything the routes share: one database client, the models, the embedder and the task list
def build_state(settings: Settings, embedder: Embedder | None = None) -> AppState:
    database = GraphDatabase(settings.falkordb_url)
    return AppState(
        settings=settings,
        database=database,
        models=ModelFactory(settings, database),
        embedder=embedder or LocalEmbedder(settings.embedding_model, settings.embedding_dimensions),
        tasks=TaskRegistry(),
        guard_mode=settings.guard_mode,
    )


# Builds the API, mounts the MCP tools at /mcp when switched on, and serves the built web app
def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    settings = settings or get_settings()
    state = build_state(settings, embedder)
    mcp = (
        build_mcp_server(state.buyer_session(settings.mcp_buyer_id))
        if settings.mcp_over_http
        else None
    )

    # Starts the MCP session manager if it is mounted, and closes the database on the way out
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with contextlib.AsyncExitStack() as stack:
            if mcp is not None:
                await stack.enter_async_context(mcp.session_manager.run())
            yield
            await state.database.close()

    app = FastAPI(title="TRACE-Graph", version="0.1.0", lifespan=lifespan)
    app.state.tracegraph = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(GraphUnavailableError, graph_unavailable)
    for module in (ops, tasks, graph_views, investigator, scoreboard, admin):
        app.include_router(module.router)
    if mcp is not None:
        security = TransportSecuritySettings(allowed_hosts=settings.mcp_allowed_hosts)
        app.mount(
            "/mcp", mcp.streamable_http_app(streamable_http_path="/", transport_security=security)
        )
    if Path(settings.web_dir, "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app


# FalkorDB down means the API says so plainly, instead of a stack trace
async def graph_unavailable(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse({"detail": f"FalkorDB is unavailable: {error}"}, status_code=503)


# Entry point for the tracegraph-api command
def run() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)
