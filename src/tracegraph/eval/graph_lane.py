import time

from tracegraph.agent.assembly import build_marketplace
from tracegraph.agent.loop import BuyerAgent
from tracegraph.agent.session import AgentSession
from tracegraph.config import Settings
from tracegraph.eval.agent_cases import AgentCase
from tracegraph.eval.case_market import AGENT_BUYER, case_market
from tracegraph.eval.case_runs import CaseRun, graph_case_run
from tracegraph.eval.stand_ins import StandInModels
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.chat import ChatModel
from tracegraph.llm.embeddings import Embedder
from tracegraph.market.providers import Behaviour
from tracegraph.market.seed import write_market
from tracegraph.market.tasks import PlannedJob
from tracegraph.trace.settings import TraceSettings


# The same model with the FalkorDB tools: one case, one job, on its own graph
async def run_graph_case(
    database: GraphDatabase,
    settings: Settings,
    model: ChatModel,
    embedder: Embedder,
    case: AgentCase,
) -> CaseRun:
    graph = f"agent-eval:{case.case_id}"
    await database.delete_graph(graph)
    spec = case_market(case, time.time())
    await write_market(database, graph, spec, embedder.dimensions)
    try:
        agent = BuyerAgent(
            case_session(database, settings, graph, embedder, spec.behaviours), model
        )
        job = PlannedJob(f"{case.case_id}-summarise", "summarise", case.text)
        task_run = await agent.run_plan(case.case_id, f"Summarise: {case.text}", [job])
    finally:
        await database.delete_graph(graph)
    run = graph_case_run(case.case_id, case.kind, case.label, task_run.jobs[0])
    if run.hired is not None:
        run.hired_malicious = run.hired in case.malicious
        run.sats_to_scam = case.price_of(run.hired) if run.hired_malicious else 0
    return run


# Buyer 1's session on a case graph, with providers and judge that need no LLM
def case_session(
    database: GraphDatabase,
    settings: Settings,
    graph: str,
    embedder: Embedder,
    behaviours: dict[str, Behaviour],
) -> AgentSession:
    case_settings = settings.model_copy(update={"shared_graph": graph, "guard_mode": "closed"})
    trace_settings = TraceSettings()
    marketplace = build_marketplace(
        database, graph, StandInModels(), trace_settings.hireable_count, behaviours
    )
    return AgentSession(
        database,
        case_settings,
        AGENT_BUYER,
        marketplace=marketplace,
        embedder=embedder,
        trace_settings=trace_settings,
    )
