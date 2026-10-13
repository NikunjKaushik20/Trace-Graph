from typing import Literal

from mcp.server.mcpserver import MCPServer

from tracegraph.agent import tool_descriptions as describe
from tracegraph.agent.mcp_server import Result, guarded
from tracegraph.agent.session import AgentSession
from tracegraph.agent.tools import explaining, views
from tracegraph.evidence.rules import GuardMode


# The investigator's MCP server: eight read-only tools, so a question can never move money
def build_investigator_server(session: AgentSession) -> MCPServer:
    server = MCPServer(
        name="tracegraph-investigator", instructions=describe.INVESTIGATOR_INSTRUCTIONS
    )
    add_lookup_tools(server, session)
    add_decision_tools(server, session)
    return server


# recent_jobs, job_story, funding_chain, neighbourhood and quarantines
def add_lookup_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: the newest jobs and how they ended
    @server.tool(name="recent_jobs", description=describe.RECENT_JOBS)
    async def recent_jobs(
        payment_status: Literal["released", "refunded", "held"] | None = None,
    ) -> Result:
        return await guarded(views.recent_jobs(session, payment_status))

    # Tool: one job from task to outcome
    @server.tool(name="job_story", description=describe.JOB_STORY)
    async def job_story(job_id: str) -> Result:
        return await guarded(views.job_story(session, job_id))

    # Tool: the money behind a node
    @server.tool(name="funding_chain", description=describe.FUNDING_CHAIN)
    async def funding_chain(node_id: str) -> Result:
        return await guarded(views.funding_chain(session, node_id))

    # Tool: what a node is connected to
    @server.tool(name="neighbourhood", description=describe.NEIGHBOURHOOD)
    async def neighbourhood(node_id: str, hops: int = 1) -> Result:
        return await guarded(views.neighbourhood(session, node_id, hops))

    # Tool: the quarantines in force and why
    @server.tool(name="quarantines", description=describe.QUARANTINES)
    async def quarantines(provider_id: str | None = None) -> Result:
        return await guarded(views.quarantines(session, provider_id))


# explain_decision, what_if and who_authorised
def add_decision_tools(server: MCPServer, session: AgentSession) -> None:
    # Tool: the receipt for a decision
    @server.tool(name="explain_decision", description=describe.EXPLAIN_DECISION)
    async def explain_decision(decision_id: str) -> Result:
        return await guarded(explaining.explain_decision(session, decision_id))

    # Tool: the same decision with a different guard
    @server.tool(name="what_if", description=describe.WHAT_IF)
    async def what_if(decision_id: str, guard: GuardMode = "unguarded") -> Result:
        return await guarded(explaining.what_if(session, decision_id, guard))

    # Tool: who stands behind a payment
    @server.tool(name="who_authorised", description=describe.WHO_AUTHORISED)
    async def who_authorised(payment_id: str) -> Result:
        return await guarded(explaining.who_authorised(session, payment_id))
