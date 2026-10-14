from tracegraph.agent.runs import JobRun, ToolStep
from tracegraph.eval.agent_cases import build_cases
from tracegraph.eval.agent_scores import lane_score, tool_choice_score
from tracegraph.eval.case_runs import CaseRun, graph_case_run
from tracegraph.eval.stand_ins import CannedWorker, OverlapJudge
from tracegraph.eval.text_lane import reviews_as_text, run_text_case
from tracegraph.llm.text_model import ScriptedModel
from tracegraph.market.judge import judge_delivery
from tracegraph.market.providers import ScamWork
from tracegraph.market.work import Delivery, WorkOrder, parse_json_object

RING_CASE = next(case for case in build_cases() if case.label == "ring")
TEXT = RING_CASE.text


async def test_the_stand_in_judge_passes_real_work_and_fails_canned_scam_output() -> None:
    order = WorkOrder("job-1", "summarise", TEXT, 10)
    honest = parse_json_object(await CannedWorker().complete("system", TEXT))
    scam = await ScamWork().perform(order)
    passed = await judge_delivery(order, Delivery("job-1", "prov-a", honest), OverlapJudge())
    failed = await judge_delivery(order, Delivery("job-1", "prov-b", scam), OverlapJudge())
    assert passed.passed and not failed.passed


def test_the_text_lane_sees_every_provider_and_review_but_no_funding() -> None:
    text = reviews_as_text(RING_CASE)
    for provider in RING_CASE.providers:
        assert provider.provider_id in text
    assert "writer-01: job done, 5 stars" in text
    assert "wallet" not in text and "root" not in text


async def test_the_text_lane_records_a_scam_pick_and_its_price() -> None:
    scam = sorted(RING_CASE.malicious)[0]
    model = ScriptedModel(lambda system, prompt: f'{{"provider_id": "{scam}", "reason": "cheap"}}')
    run = await run_text_case(model, RING_CASE)
    assert run.hired == scam and run.hired_malicious
    assert run.sats_to_scam == RING_CASE.price_of(scam)


async def test_a_text_reply_naming_nobody_is_an_error_not_a_hire() -> None:
    run = await run_text_case(ScriptedModel(lambda system, prompt: "I am not sure."), RING_CASE)
    assert run.hired is None and run.error is not None


def test_the_graph_run_reads_hire_and_investigation_from_the_tool_steps() -> None:
    steps = [
        ToolStep("trace_score", {}, True, {"decision_id": "dec-1"}),
        ToolStep("funding_path", {}, True, {}),
        ToolStep("find_ring", {}, True, {}),
        ToolStep("quarantine", {}, True, {"policy_id": "policy-1"}),
        ToolStep("hire_with_escrow", {}, True, {"provider_id": "prov-amber"}),
    ]
    run = graph_case_run(
        "case-001", "ring", "ring", JobRun("case-001-summarise", "summarise", steps)
    )
    assert run.hired == "prov-amber"
    assert run.investigated and run.quarantined and run.quarantine_backed


def test_l1_and_l2_scores_count_what_happened() -> None:
    runs = [
        CaseRun("c1", "ring", "ring", "graph", "prov-a", investigated=True, quarantined=True),
        CaseRun("c2", "ring", "ring", "graph", "prov-x", True, 6),
        CaseRun("c3", "clean", "clean", "graph", "prov-b", investigated=True),
        CaseRun("c4", "clean", "clean", "graph", None),
    ]
    l1 = lane_score("graph", runs)
    assert (l1.scams_hired, l1.sats_to_scams, l1.rings_hired, l1.no_hire) == (1, 6, 1, 1)
    l2 = tool_choice_score(runs)
    assert (l2.rings_investigated, l2.other_cases_investigated) == (1, 1)
    assert (l2.precision, l2.recall) == (0.5, 0.5)
    assert (l2.quarantines, l2.false_quarantines) == (1, 0)
