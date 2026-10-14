from mcp.client.client import Client

from tests.agent.fakes import ScriptedChatModel
from tracegraph.agent.investigator import Investigator
from tracegraph.agent.investigator_server import build_investigator_server
from tracegraph.agent.session import AgentSession
from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.policies import ACTIVE_POLICIES
from tracegraph.graph.queries.receipts import DECISION_RECEIPT, WHO_AUTHORISED
from tracegraph.graph.queries.views import FUNDING_CHAIN, JOB_STORY, NEIGHBOURHOOD, RECENT_JOBS
from tracegraph.llm.chat import ChatReply

NOWHERE = "redis://127.0.0.1:1"


# A read-only session on a database that is not there
def observer() -> AgentSession:
    return AgentSession(GraphDatabase(NOWHERE), Settings(falkordb_url=NOWHERE), "observer")


async def test_the_investigator_gets_eight_lookups_and_nothing_that_moves_money() -> None:
    async with Client(build_investigator_server(observer())) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
    assert names == {
        "recent_jobs",
        "job_story",
        "explain_decision",
        "what_if",
        "who_authorised",
        "funding_chain",
        "neighbourhood",
        "quarantines",
    }


def test_every_query_behind_the_investigator_is_read_only() -> None:
    queries = [
        RECENT_JOBS,
        JOB_STORY,
        FUNDING_CHAIN,
        NEIGHBOURHOOD,
        DECISION_RECEIPT,
        WHO_AUTHORISED,
        ACTIVE_POLICIES,
    ]
    assert all(query.read_only for query in queries)


async def test_an_answer_with_no_ids_and_no_tools_is_kept_as_it_is() -> None:
    model = ScriptedChatModel([ChatReply("The graph has nothing on that question.")])
    answer = await Investigator(observer(), model, max_steps=4).ask("What is the weather?")
    assert answer.answer == "The graph has nothing on that question."
    assert answer.citations.passed
    assert answer.path_ids == []
    assert answer.as_dict()["tools"] == []


async def test_an_empty_answer_falls_back_to_the_records_seen() -> None:
    model = ScriptedChatModel([ChatReply(""), ChatReply("")])
    answer = await Investigator(observer(), model, max_steps=4).ask("Who funds prov-summa?")
    assert answer.citations.fell_back_to_receipt
    assert "Records looked at: none" in answer.answer
