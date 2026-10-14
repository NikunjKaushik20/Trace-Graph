from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tracegraph.agent.runs import AgentEvent
from tracegraph.api.routes.tasks import next_task_id
from tracegraph.api.server import create_app
from tracegraph.api.task_runs import TaskHandle
from tracegraph.config import Settings
from tracegraph.llm.embeddings import HashingEmbedder

ADMIN = {"admin-token": "letmein"}


# The API pointed at a port where nothing listens, so FalkorDB is always down
@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        falkordb_url="redis://127.0.0.1:1",
        llm_mode="replay",
        replay_path=str(tmp_path / "empty.json"),
        admin_token="letmein",
        embedding_dimensions=8,
    )
    with TestClient(create_app(settings, HashingEmbedder(8))) as test_client:
        yield test_client


def test_health_fails_closed_when_falkordb_is_down(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["falkordb"] == "down"
    assert response.json()["can_pay"] is False


def test_a_graph_read_with_falkordb_down_is_a_503_not_a_crash(client: TestClient) -> None:
    response = client.get("/decisions/dec-x-1/receipt")
    assert response.status_code == 503
    assert "FalkorDB is unavailable" in response.json()["detail"]


def test_admin_routes_need_the_token(client: TestClient) -> None:
    assert client.post("/admin/guard", json={"mode": "open"}).status_code == 403
    wrong = client.post("/admin/guard", json={"mode": "open"}, headers={"admin-token": "nope"})
    assert wrong.status_code == 403
    right = client.post("/admin/guard", json={"mode": "unguarded"}, headers=ADMIN)
    assert right.json() == {"guard_mode": "unguarded"}
    assert client.get("/health").json()["guard_mode"] == "unguarded"


def test_admin_routes_are_off_without_a_configured_token(tmp_path: Path) -> None:
    settings = Settings(falkordb_url="redis://127.0.0.1:1", admin_token="")
    with TestClient(create_app(settings, HashingEmbedder(8))) as test_client:
        response = test_client.post("/admin/plug", json={"connected": False}, headers=ADMIN)
    assert response.status_code == 403


def test_pulling_the_plug_is_reported_by_health(client: TestClient) -> None:
    client.post("/admin/plug", json={"connected": False}, headers=ADMIN)
    assert client.get("/health").json()["unplugged"] is True
    client.post("/admin/plug", json={"connected": True}, headers=ADMIN)
    assert client.get("/health").json()["unplugged"] is False


def test_bad_input_is_refused_before_anything_runs(client: TestClient) -> None:
    assert (
        client.post("/tasks", json={"buyer_id": "buyer-9", "text": "Summarise: x"}).status_code
        == 422
    )
    assert client.get("/scoreboard/live", params={"lane": "nonsense"}).status_code == 422
    assert client.get("/nodes/prov-summa/neighbourhood", params={"hops": 5}).status_code == 422
    assert client.get("/tasks/task-missing").status_code == 404
    assert client.get("/tasks/task-missing/events").status_code == 404


def test_a_task_with_falkordb_down_is_refused_before_it_starts(client: TestClient) -> None:
    body = {"buyer_id": "buyer-1", "text": "Summarise: graphs are useful", "task_id": "task-down"}
    refused = client.post("/tasks", json=body)
    assert refused.status_code == 503
    assert "FalkorDB is unavailable" in refused.json()["detail"]
    assert client.get("/tasks/task-down").status_code == 404


async def test_a_follower_gets_past_events_then_live_ones_then_stops() -> None:
    handle = TaskHandle("task-1", "buyer-1", "Summarise: x")
    await handle.publish(AgentEvent("plan", "buyer-1", None, {}))
    follower = handle.follow()
    seen = [await anext(follower)]
    await handle.publish(AgentEvent("tool_call", "buyer-1", "job-1", {}))
    await handle.finish(None)
    seen += [item async for item in follower]
    assert [(index, event.kind) for index, event in seen] == [(0, "plan"), (1, "tool_call")]


def test_the_buyer_tools_are_served_over_http_at_mcp_when_switched_on(tmp_path: Path) -> None:
    settings = Settings(
        falkordb_url="redis://127.0.0.1:1",
        mcp_over_http=True,
        mcp_allowed_hosts=["testserver"],
        llm_mode="replay",
        replay_path=str(tmp_path / "empty.json"),
    )
    hello = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }
    accept = {"accept": "application/json, text/event-stream"}
    with TestClient(create_app(settings, HashingEmbedder(8))) as test_client:
        response = test_client.post("/mcp/", json=hello, headers=accept)
    assert response.status_code == 200
    assert "tracegraph-buyer-1" in response.text


def test_a_live_lane_with_falkordb_down_streams_an_error_event(client: TestClient) -> None:
    params = {"lane": "guarded", "seed": 1000}
    with client.stream("GET", "/scoreboard/live", params=params) as stream:
        events = [line for line in stream.iter_lines() if line.startswith("event:")]
    assert events == ["event: error"]
    assert client.app.state.tracegraph.live_lanes == 0  # type: ignore[attr-defined]


def test_live_lanes_are_capped(client: TestClient) -> None:
    client.app.state.tracegraph.live_lanes = 2  # type: ignore[attr-defined]
    response = client.get("/scoreboard/live", params={"lane": "guarded"})
    assert response.status_code == 429


def test_errors_never_show_the_database_password(tmp_path: Path) -> None:
    settings = Settings(falkordb_url="redis://default:s3cret@127.0.0.1:1")
    with TestClient(create_app(settings, HashingEmbedder(8))) as test_client:
        response = test_client.get("/decisions/dec-x-1/receipt")
    assert response.status_code == 503
    assert "s3cret" not in response.text
    assert "127.0.0.1:1" in response.text


def test_task_numbers_carry_on_after_the_highest_one_taken() -> None:
    assert next_task_id(set()) == "task-1"
    assert next_task_id({"task-1", "task-9", "task-3", "eval-case-12"}) == "task-10"
