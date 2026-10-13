import asyncio
from collections.abc import Awaitable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tracegraph.agent import tool_descriptions as describe
from tracegraph.agent.assembly import build_session
from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.agent.tools import acting, deciding, explaining, investigating, remembering
from tracegraph.config import get_settings
from tracegraph.graph.connection import GraphDatabase, GraphUnavailableError
from tracegraph.llm.embeddings import LocalEmbedder
from tracegraph.llm.factory import ModelFactory

Result = dict[str, Any]


# Runs a tool and turns refusals and a missing database into errors the agent can read
async def guarded(work: Awaitable[Result]) -> Result:
    try:
        return await work
    except ToolRefusedError as error:
        raise ToolError(f"refused: {error}") from error
    except GraphUnavailableError as error:
        raise ToolError("FalkorDB is unreachable, so nothing can be scored or paid") from error


# Builds the MCP server for one buyer session, with all 11 tools
def build_mcp_server(session: AgentSession) -> MCPServer:
    server = MCPServer(
        name=f"tracegraph-{session.buyer_id}", instructions=describe.SERVER_INSTRUCTIONS
    )
    add_memory_tools(server, session)
    add_decision_tools(server, session)
    add_investigation_tools(server, session)
    add_action_tools(server, session)
    add_explanation_tools(server, session)
    return server


# recall_memory and write_lesson
def add_memory_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: what the buyer remembers
    @server.tool(name="recall_memory", description=describe.RECALL_MEMORY)
    async def recall_memory(task_text: str) -> Result:
        return await guarded(remembering.recall_memory(session, task_text))

    # Tool: save a lesson backed by evidence
    @server.tool(name="write_lesson", description=describe.WRITE_LESSON)
    async def write_lesson(text: str, evidence_ids: list[str]) -> Result:
        return await guarded(remembering.write_lesson(session, text, evidence_ids))


# find_providers and trace_score
def add_decision_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: providers for a capability
    @server.tool(name="find_providers", description=describe.FIND_PROVIDERS)
    async def find_providers(capability: str) -> Result:
        return await guarded(deciding.find_providers(session, capability))

    # Tool: TRACE scores and the decision
    @server.tool(name="trace_score", description=describe.TRACE_SCORE)
    async def trace_score(job_id: str) -> Result:
        return await guarded(deciding.trace_score(session, job_id))


# funding_path, find_ring and quarantine
def add_investigation_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: follow the money
    @server.tool(name="funding_path", description=describe.FUNDING_PATH)
    async def funding_path(decision_id: str, writer_id: str, provider_id: str) -> Result:
        return await guarded(
            investigating.funding_path(session, decision_id, writer_id, provider_id)
        )

    # Tool: find a ring
    @server.tool(name="find_ring", description=describe.FIND_RING)
    async def find_ring(decision_id: str, provider_id: str) -> Result:
        return await guarded(investigating.find_ring(session, decision_id, provider_id))

    # Tool: quarantine a ring for everyone
    @server.tool(name="quarantine", description=describe.QUARANTINE)
    async def quarantine(decision_id: str, ring_id: str, reason: str) -> Result:
        return await guarded(investigating.quarantine(session, decision_id, ring_id, reason))


# hire_with_escrow and settle
def add_action_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: pay into escrow and get the work
    @server.tool(name="hire_with_escrow", description=describe.HIRE_WITH_ESCROW)
    async def hire_with_escrow(job_id: str, provider_id: str) -> Result:
        return await guarded(acting.hire_with_escrow(session, job_id, provider_id))

    # Tool: judge, then release or refund
    @server.tool(name="settle", description=describe.SETTLE)
    async def settle(job_id: str) -> Result:
        return await guarded(acting.settle(session, job_id))


# explain_decision and who_authorised
def add_explanation_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: the receipt for a decision
    @server.tool(name="explain_decision", description=describe.EXPLAIN_DECISION)
    async def explain_decision(decision_id: str) -> Result:
        return await guarded(explaining.explain_decision(session, decision_id))

    # Tool: who stands behind a payment
    @server.tool(name="who_authorised", description=describe.WHO_AUTHORISED)
    async def who_authorised(payment_id: str) -> Result:
        return await guarded(explaining.who_authorised(session, payment_id))


# Serves one buyer's tools over stdio, for MCP clients such as Claude Desktop or an IDE
async def serve_stdio() -> None:
    settings = get_settings()
    database = GraphDatabase(settings.falkordb_url)
    embedder = LocalEmbedder(settings.embedding_model, settings.embedding_dimensions)
    models = ModelFactory(settings, database)
    session = build_session(settings, database, settings.mcp_buyer_id, models, embedder=embedder)
    try:
        await build_mcp_server(session).run_stdio_async()
    finally:
        await database.close()


# Entry point for the tracegraph-mcp command
def run_stdio() -> None:
    asyncio.run(serve_stdio())
