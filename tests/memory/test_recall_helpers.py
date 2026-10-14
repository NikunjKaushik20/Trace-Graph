import math

from tracegraph.llm.embeddings import HashingEmbedder
from tracegraph.memory.recall import lesson_from_row


# A lesson row the way the recall queries return it
def lesson_row(lesson_id: str, subjects: list[str], ring_providers: list[str]) -> dict[str, object]:
    return {
        "lesson_id": lesson_id,
        "text": "Avoid cheap providers praised only by new writers.",
        "author_id": "buyer-1",
        "source_ids": ["dec-1"],
        "subject_ids": subjects,
        "ring_provider_ids": ring_providers,
    }


def test_a_lesson_about_a_ring_counts_when_a_ring_member_is_a_candidate() -> None:
    row = lesson_row("lesson-1", ["ring-abc"], ["prov-quickdigest", "prov-tagstar"])
    assert lesson_from_row(row, ["prov-summa", "prov-quickdigest"]).about_todays_candidates
    assert not lesson_from_row(row, ["prov-summa"]).about_todays_candidates


def test_a_lesson_about_a_provider_counts_when_that_provider_is_a_candidate() -> None:
    row = lesson_row("lesson-2", ["prov-cheaptags"], [])
    assert lesson_from_row(row, ["prov-cheaptags"]).about_todays_candidates


async def test_hashing_embedder_gives_unit_vectors_and_rewards_shared_words() -> None:
    embedder = HashingEmbedder(dimensions=16)
    first, close, far = await embedder.embed(
        ["refund the cheap summary ring", "cheap summary ring refund", "translate french poetry"]
    )
    assert math.isclose(sum(value * value for value in first), 1.0)
    similarity_close = sum(a * b for a, b in zip(first, close, strict=True))
    similarity_far = sum(a * b for a, b in zip(first, far, strict=True))
    assert similarity_close > similarity_far
