from pathlib import Path

import pytest

from tests.agent.fakes import ScriptedChatModel
from tracegraph.llm.chat import ChatReply, ToolCall
from tracegraph.llm.replay import RecordingModel, ReplayModel, ReplayStore
from tracegraph.llm.text_model import LlmUnavailableError


async def test_a_recorded_run_plays_back_in_order(tmp_path: Path) -> None:
    replies = [
        ChatReply(None, [ToolCall("c1", "trace_score", {"job_id": "job-1"})]),
        ChatReply("Done."),
    ]
    store = ReplayStore(tmp_path / "run.json")
    recorder = RecordingModel(ScriptedChatModel(replies), store, "buyer-1")
    for _ in replies:
        await recorder.chat([{"role": "user", "content": "x"}], None)

    replay = ReplayModel(ReplayStore(tmp_path / "run.json"), "buyer-1")
    first = await replay.chat([], None)
    second = await replay.chat([], None)
    assert first.tool_calls[0].arguments == {"job_id": "job-1"}
    assert second.content == "Done."
    with pytest.raises(LlmUnavailableError):
        await replay.chat([], None)


async def test_channels_replay_independently(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "run.json")
    store.append("judge", ChatReply("PASS: ok"))
    store.append("buyer-1", ChatReply("hello"))
    assert await ReplayModel(store, "judge").complete("s", "p") == "PASS: ok"
    assert await ReplayModel(store, "buyer-1").complete("s", "p") == "hello"
