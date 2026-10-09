import secrets
import time
from dataclasses import dataclass

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.memory import CLASSIFY_EVIDENCE, WRITE_LESSON
from tracegraph.llm.embeddings import Embedder

SOURCE_KINDS = {"Decision", "Policy"}
SUBJECT_KINDS = {"Provider", "Ring"}


class LessonRefusedError(RuntimeError):
    pass


@dataclass(frozen=True)
class LessonDraft:
    buyer_id: str
    text: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class SavedLesson:
    lesson_id: str
    source_ids: list[str]
    subject_ids: list[str]


# Saves a lesson only if every id it cites exists and at least one is a decision or policy
async def write_lesson(
    database: GraphDatabase,
    graph_name: str,
    draft: LessonDraft,
    embedder: Embedder,
    timer: GraphTimer | None = None,
) -> SavedLesson:
    text = draft.text.strip()
    if not text:
        raise LessonRefusedError("a lesson needs some text")
    kinds = await classify_evidence(database, graph_name, draft.evidence_ids, timer)
    unknown = [evidence_id for evidence_id, kind in kinds.items() if kind is None]
    if unknown:
        raise LessonRefusedError(f"these ids are not in the graph: {', '.join(unknown)}")
    source_ids = [evidence_id for evidence_id, kind in kinds.items() if kind in SOURCE_KINDS]
    subject_ids = [evidence_id for evidence_id, kind in kinds.items() if kind in SUBJECT_KINDS]
    if not source_ids:
        raise LessonRefusedError("a lesson must cite at least one decision or policy")
    [embedding] = await embedder.embed([text])
    params = {
        "buyer_id": draft.buyer_id,
        "lesson_id": f"lesson-{secrets.token_hex(5)}",
        "text": text,
        "t": time.time(),
        "embedding": embedding,
        "source_ids": source_ids,
        "subject_ids": subject_ids,
    }
    rows = await database.rows(graph_name, WRITE_LESSON, params, timer)
    if not rows:
        raise LessonRefusedError(f"buyer {draft.buyer_id} is not in this graph")
    return SavedLesson(str(rows[0]["lesson_id"]), source_ids, subject_ids)


# Looks up what kind of node each id is; None for ids the graph does not have
async def classify_evidence(
    database: GraphDatabase, graph_name: str, ids: list[str], timer: GraphTimer | None = None
) -> dict[str, str | None]:
    unique_ids = list(dict.fromkeys(ids))
    rows = await database.rows(graph_name, CLASSIFY_EVIDENCE, {"ids": unique_ids}, timer)
    return {str(row["id"]): row["kind"] for row in rows}
