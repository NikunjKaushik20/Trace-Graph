from dataclasses import asdict
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.graph.connection import GraphTimer
from tracegraph.memory.lessons import LessonDraft, LessonRefusedError
from tracegraph.memory.lessons import write_lesson as save_lesson
from tracegraph.memory.recall import RecallRequest
from tracegraph.memory.recall import recall_memory as recall_from_graph


# What this buyer remembers: its past decisions, pooled trust, quarantines in force, and lessons
async def recall_memory(session: AgentSession, task_text: str) -> dict[str, Any]:
    timer = GraphTimer()
    request = RecallRequest(session.graph_name, session.buyer_id, task_text)
    memory = await recall_from_graph(session.database, request, session.embedder, timer)
    return {
        "past_decisions": memory.past_decisions,
        "pooled_trust": memory.pooled_trust,
        "quarantines": [asdict(policy) for policy in memory.policies],
        "lessons": [asdict(lesson) for lesson in memory.lessons],
        "graph_ms": timer.total_ms,
    }


# Saves a lesson linked to the decisions, policies, providers or rings that taught it
async def write_lesson(session: AgentSession, text: str, evidence_ids: list[str]) -> dict[str, Any]:
    if session.embedder is None:
        raise ToolRefusedError("this session has no embedder, so lessons cannot be saved")
    timer = GraphTimer()
    draft = LessonDraft(session.buyer_id, text, evidence_ids)
    try:
        saved = await save_lesson(
            session.database, session.graph_name, draft, session.embedder, timer
        )
    except LessonRefusedError as error:
        raise ToolRefusedError(str(error)) from error
    return {**asdict(saved), "graph_ms": timer.total_ms}
