from mcp.client.client import Client

from tracegraph.agent.mcp_server import build_mcp_server
from tracegraph.agent.session import AgentSession
from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase

ELEVEN_TOOLS = {
    "recall_memory",
    "find_providers",
    "trace_score",
    "funding_path",
    "find_ring",
    "hire_with_escrow",
    "settle",
    "quarantine",
    "write_lesson",
    "explain_decision",
    "who_authorised",
}


# A session pointed at a port where nothing is listening, as if FalkorDB were switched off
def session_without_database() -> AgentSession:
    return AgentSession(GraphDatabase("redis://127.0.0.1:6391"), Settings(), "buyer-1")


async def test_the_server_offers_exactly_the_eleven_tools() -> None:
    async with Client(build_mcp_server(session_without_database())) as client:
        tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == ELEVEN_TOOLS
    assert all(tool.description for tool in tools)


async def test_without_falkordb_the_agent_cannot_score_or_pay() -> None:
    async with Client(build_mcp_server(session_without_database())) as client:
        scored = await client.call_tool("trace_score", {"job_id": "t1-summarise"})
        hired = await client.call_tool("hire_with_escrow", {"job_id": "t1", "provider_id": "p"})
    assert scored.is_error and "FalkorDB is unreachable" in scored.content[0].text
    assert hired.is_error
