from dataclasses import dataclass, field
from typing import Any

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.memory import (
    PAST_DECISIONS,
    POOLED_TRUST,
    RECENT_LESSONS,
    SIMILAR_LESSONS,
)
from tracegraph.investigation.quarantine import QuarantinePolicy, active_policies
from tracegraph.llm.embeddings import Embedder


@dataclass(frozen=True)
class RecalledLesson:
    lesson_id: str
    text: str
    author_id: str | None
    source_ids: list[str]
    subject_ids: list[str]
    about_todays_candidates: bool


@dataclass
class MemoryRecall:
    past_decisions: list[dict[str, Any]] = field(default_factory=list)
    pooled_trust: list[dict[str, Any]] = field(default_factory=list)
    policies: list[QuarantinePolicy] = field(default_factory=list)
    lessons: list[RecalledLesson] = field(default_factory=list)


@dataclass(frozen=True)
class RecallRequest:
    graph_name: str
    buyer_id: str
    task_text: str
    candidate_ids: list[str] = field(default_factory=list)
    decision_limit: int = 10
    lesson_limit: int = 5


# Everything a buyer remembers at the start of a session: what it did, whom it trusts, the rules
async def recall_memory(
    database: GraphDatabase,
    request: RecallRequest,
    embedder: Embedder | None,
    timer: GraphTimer | None = None,
) -> MemoryRecall:
    graph = request.graph_name
    buyer = {"buyer_id": request.buyer_id}
    decisions = await database.rows(
        graph, PAST_DECISIONS, {**buyer, "limit": request.decision_limit}, timer
    )
    trust = await database.rows(graph, POOLED_TRUST, buyer, timer)
    policies = await active_policies(database, graph, timer)
    lessons = await recall_lessons(database, request, embedder, timer)
    return MemoryRecall(decisions, trust, policies, lessons)


# Lessons closest to the task by vector search, with ones about today's candidates moved first
async def recall_lessons(
    database: GraphDatabase,
    request: RecallRequest,
    embedder: Embedder | None,
    timer: GraphTimer | None = None,
) -> list[RecalledLesson]:
    if embedder is None:
        params: dict[str, Any] = {"k": request.lesson_limit}
        rows = await database.rows(request.graph_name, RECENT_LESSONS, params, timer)
    else:
        [query_vector] = await embedder.embed([request.task_text])
        params = {"k": request.lesson_limit, "query_vector": query_vector}
        rows = await database.rows(request.graph_name, SIMILAR_LESSONS, params, timer)
    lessons = [lesson_from_row(row, request.candidate_ids) for row in rows]
    return sorted(lessons, key=lambda lesson: not lesson.about_todays_candidates)


# Turns one lesson row into a RecalledLesson, noting if it is about any candidate in play
def lesson_from_row(row: dict[str, Any], candidate_ids: list[str]) -> RecalledLesson:
    subject_ids = [str(subject) for subject in row["subject_ids"] or []]
    ring_providers = [str(provider) for provider in row.get("ring_provider_ids") or []]
    return RecalledLesson(
        lesson_id=str(row["lesson_id"]),
        text=str(row["text"]),
        author_id=row["author_id"],
        source_ids=[str(source) for source in row["source_ids"] or []],
        subject_ids=subject_ids,
        about_todays_candidates=bool(set(subject_ids + ring_providers) & set(candidate_ids)),
    )
