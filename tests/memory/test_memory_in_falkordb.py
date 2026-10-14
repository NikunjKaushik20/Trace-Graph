import pytest

from tests.investigation.test_investigation_in_falkordb import market_with_a_decision
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.embeddings import HashingEmbedder
from tracegraph.memory.lessons import LessonDraft, LessonRefusedError, write_lesson
from tracegraph.memory.recall import RecallRequest, recall_memory

pytestmark = pytest.mark.falkordb

EMBEDDER = HashingEmbedder(dimensions=8)


async def test_a_lesson_must_cite_real_nodes_and_a_decision(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    with pytest.raises(LessonRefusedError, match="not in the graph"):
        await write_lesson(database, graph_name, LessonDraft("buyer-1", "x", ["dec-404"]), EMBEDDER)
    with pytest.raises(LessonRefusedError, match="decision or policy"):
        await write_lesson(
            database, graph_name, LessonDraft("buyer-1", "x", ["prov-summa"]), EMBEDDER
        )


async def test_a_lesson_may_cite_the_payment_and_job_behind_its_decision(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    evidence = ["dec-1", "pay-job-past-prov-summa-0", "job-past-prov-summa-0"]
    draft = LessonDraft("buyer-1", "Summa delivered; paying it again is safe.", evidence)
    saved = await write_lesson(database, graph_name, draft, EMBEDDER)
    assert saved.source_ids == ["dec-1"]


async def test_a_saved_lesson_comes_back_in_the_next_session(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    draft = LessonDraft(
        "buyer-1",
        "QuickDigest's praise comes from writers funded by its own hub; do not hire it.",
        ["dec-1", "prov-quickdigest"],
    )
    saved = await write_lesson(database, graph_name, draft, EMBEDDER)
    assert saved.source_ids == ["dec-1"]
    assert saved.subject_ids == ["prov-quickdigest"]

    request = RecallRequest(
        graph_name, "buyer-1", "summarise this page", candidate_ids=["prov-quickdigest"]
    )
    memory = await recall_memory(database, request, EMBEDDER)
    assert memory.lessons[0].lesson_id == saved.lesson_id
    assert memory.lessons[0].about_todays_candidates
    assert memory.past_decisions[0]["decision_id"] == "dec-1"
    without_vectors = await recall_memory(database, request, None)
    assert without_vectors.lessons[0].lesson_id == saved.lesson_id
