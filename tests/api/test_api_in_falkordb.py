import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.agent.fakes import ScriptedChatModel
from tests.conftest import FALKORDB_URL
from tracegraph.api.server import create_app
from tracegraph.api.state import AppState
from tracegraph.config import Settings
from tracegraph.llm.chat import ChatModel, ChatReply, ToolCall
from tracegraph.llm.embeddings import HashingEmbedder
from tracegraph.market.seed import delete_market_graphs

pytestmark = pytest.mark.falkordb

ADMIN = {"admin-token": "letmein"}
RING_ANSWER = "prov-quickdigest is paid for through wallet-ring-ops, which root-ring-hub funds."


class OneModel:
    # Hands the same scripted model to every channel
    def __init__(self, model: ChatModel) -> None:
        self.model = model

    # The scripted model, whoever asks
    def model_for(self, channel: str) -> ChatModel:
        return self.model


# The API on its own throwaway graphs, seeded without the ring, deleted afterwards
@pytest.fixture
def client() -> Iterator[TestClient]:
    run = uuid.uuid4().hex[:8]
    settings = Settings(
        falkordb_url=FALKORDB_URL,
        shared_graph=f"apitest-{run}",
        ops_graph=f"apitest-ops-{run}",
        scoreboard_graph=f"apitest-scoreboard-{run}",
        results_dir=f"apitest-no-results-{run}",
        admin_token="letmein",
        embedding_dimensions=8,
        investigator_questions_per_visitor=1,
    )
    with TestClient(create_app(settings, HashingEmbedder(8))) as test_client:
        if test_client.get("/health").status_code != 200:
            pytest.skip("FalkorDB is not running")
        test_client.post("/admin/seed", json={"with_ring": False}, headers=ADMIN)
        yield test_client
        state: AppState = test_client.app.state.tracegraph  # type: ignore[attr-defined]
        test_client.portal.call(delete_market_graphs, state.database, settings.shared_graph)
        test_client.portal.call(state.database.delete_graph, settings.ops_graph)


# The ids of every node in the shared market snapshot
def snapshot_ids(client: TestClient) -> set[str]:
    return {node["id"] for node in client.get("/graph/snapshot").json()["nodes"]}


def test_the_ring_arrives_only_when_the_admin_says_so(client: TestClient) -> None:
    assert "prov-quickdigest" not in snapshot_ids(client)
    arrived = client.post("/admin/ring", headers=ADMIN).json()
    assert arrived["providers"] == ["prov-quickdigest", "prov-tagstar", "prov-transfast"]
    assert {"prov-quickdigest", "sybil-01", "root-ring-hub"} <= snapshot_ids(client)
    funding = client.get("/nodes/prov-quickdigest/funding").json()
    assert ["prov-quickdigest", "wallet-ring-ops", "root-ring-hub"] in funding["chains"]


def test_the_investigator_answers_from_the_graph_and_counts_questions(client: TestClient) -> None:
    client.post("/admin/ring", headers=ADMIN)
    look = ToolCall("call-1", "funding_chain", {"node_id": "prov-quickdigest"})
    model = ScriptedChatModel([ChatReply(None, [look]), ChatReply(RING_ANSWER)])
    client.app.state.tracegraph.models = OneModel(model)  # type: ignore[attr-defined]
    question = {"question": "Who funds prov-quickdigest?"}
    answer = client.post("/investigator/ask", json=question, headers={"visitor-id": "v1"}).json()
    assert answer["answer"] == RING_ANSWER
    assert answer["citations_passed"] is True
    assert {"wallet-ring-ops", "root-ring-hub"} <= set(answer["path_ids"])
    assert answer["tools"] == [
        {"name": "funding_chain", "arguments": {"node_id": "prov-quickdigest"}, "ok": True}
    ]
    again = client.post("/investigator/ask", json=question, headers={"visitor-id": "v1"})
    assert again.status_code == 429


def test_unknown_records_are_404s_and_the_profile_shows_a_plan(client: TestClient) -> None:
    assert client.get("/decisions/dec-nothing-1/receipt").status_code == 404
    assert client.get("/decisions/dec-nothing-1/what-if").status_code == 404
    assert client.get("/payments/pay-nothing/who-authorised").status_code == 404
    profile = client.get("/profile/trace-score").json()
    assert profile["query"] == "trace_scores"
    assert profile["plan"]


def test_a_fresh_market_has_no_agent_jobs_and_no_quarantines(client: TestClient) -> None:
    assert client.get("/jobs", params={"payment_status": "released"}).json()["jobs"] == []
    assert client.get("/jobs", params={"payment_status": "lost"}).status_code == 422
    assert client.get("/quarantines").json()["policies"] == []
