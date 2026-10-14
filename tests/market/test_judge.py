from tracegraph.llm.text_model import LlmUnavailableError, ScriptedModel
from tracegraph.market.judge import judge_delivery, verdict_from_reply
from tracegraph.market.work import Delivery, WorkOrder, parse_json_object

ORDER = WorkOrder("job-1", "extract_keywords", "Graph databases store nodes and edges.", 10)


# A judge model that always gives the same reply
def judge_saying(reply: str) -> ScriptedModel:
    return ScriptedModel(lambda system, prompt: reply)


async def test_nothing_delivered_fails_before_the_llm_is_asked() -> None:
    model = judge_saying("PASS: fine")
    verdict = await judge_delivery(
        ORDER, Delivery("job-1", "p", None, "provider did not deliver"), model
    )
    assert (verdict.passed, verdict.stage) == (False, "delivery")
    assert model.calls == []


async def test_wrong_shape_fails_the_schema_check() -> None:
    model = judge_saying("PASS: fine")
    verdict = await judge_delivery(ORDER, Delivery("job-1", "p", {"keywords": ["one"]}), model)
    assert (verdict.passed, verdict.stage) == (False, "schema")
    assert model.calls == []


async def test_the_llm_check_decides_once_the_schema_passes() -> None:
    output = {"keywords": ["graph", "database", "nodes", "edges"]}
    passed = await judge_delivery(
        ORDER, Delivery("job-1", "p", output), judge_saying("PASS: on topic")
    )
    failed = await judge_delivery(
        ORDER, Delivery("job-1", "p", output), judge_saying("FAIL: generic")
    )
    assert passed.passed and passed.reason == "on topic"
    assert not failed.passed and failed.stage == "quality"


async def test_a_judge_that_cannot_run_refunds() -> None:
    # Raises the error the LLM client gives when the spend meter or endpoint stops it
    def unavailable(system: str, prompt: str) -> str:
        raise LlmUnavailableError("spend limit reached")

    output = {"keywords": ["graph", "database", "nodes"]}
    verdict = await judge_delivery(
        ORDER, Delivery("job-1", "p", output), ScriptedModel(unavailable)
    )
    assert not verdict.passed


def test_unclear_judge_replies_count_as_a_fail() -> None:
    assert not verdict_from_reply("Looks good to me").passed
    assert not verdict_from_reply("").passed
    assert verdict_from_reply("pass: ok").passed


def test_json_is_found_inside_code_fences() -> None:
    assert parse_json_object('```json\n{"summary": "x"}\n```') == {"summary": "x"}
    assert parse_json_object("no json here") is None
    assert parse_json_object("[1, 2]") is None
