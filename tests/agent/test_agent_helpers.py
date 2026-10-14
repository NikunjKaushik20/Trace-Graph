from tracegraph.agent.citations import cited_ids
from tracegraph.agent.narration import left_in_escrow, receipt_narration, remembered_note
from tracegraph.agent.planner import jobs_from_keywords, jobs_from_reply, plan_jobs
from tracegraph.agent.runs import JobRun, ToolStep
from tracegraph.llm.text_model import LlmUnavailableError, ScriptedModel


def test_cited_ids_keep_the_underscore_in_extract_keywords_ids() -> None:
    text = "Decision dec-task-2-extract_keywords-1 paid pay-task-2-extract_keywords."
    assert cited_ids(text) == ["dec-task-2-extract_keywords-1", "pay-task-2-extract_keywords"]


def test_cited_ids_finds_each_node_id_once() -> None:
    text = (
        "Decision dec-t1-summarise-1 hired prov-summa; pay-t1-summarise was released. prov-summa."
    )
    assert cited_ids(text) == ["dec-t1-summarise-1", "prov-summa", "pay-t1-summarise"]


def test_cited_ids_ignores_ordinary_hyphenated_words() -> None:
    assert cited_ids("a well-known provider with a five-star history") == []


def test_planner_keeps_known_capabilities_once_each() -> None:
    reply = (
        '{"jobs": [{"capability": "summarise", "input_text": "Graphs."},'
        ' {"capability": "summarise", "input_text": "again"},'
        ' {"capability": "write_poem", "input_text": "x"},'
        ' {"capability": "translate", "input_text": "Graphs."}]}'
    )
    jobs = jobs_from_reply(reply, "t1")
    assert [job.job_id for job in jobs] == ["t1-summarise", "t1-translate"]


def test_keyword_plan_reads_instructions_before_the_colon() -> None:
    jobs = jobs_from_keywords("t1", "Summarise and translate: a text that mentions keywords.")
    assert [job.capability for job in jobs] == ["summarise", "translate"]
    assert jobs[0].input_text == "a text that mentions keywords."


async def test_planner_falls_back_when_the_llm_is_down() -> None:
    # Fails the way the client fails when no endpoint answers
    def down(system: str, prompt: str) -> str:
        raise LlmUnavailableError("down")

    jobs = await plan_jobs(ScriptedModel(down), "t1", "Extract keywords from: graphs and nodes")
    assert [job.capability for job in jobs] == ["extract_keywords"]


# A job run with a hire and, optionally, a settle after it
def job_with_hire(settled: bool) -> JobRun:
    hire = {"provider_id": "prov-summa", "payment_id": "pay-task-1-summarise"}
    steps = [ToolStep("hire_with_escrow", {}, True, hire)]
    if settled:
        settle = {"payment_id": "pay-task-1-summarise", "status": "released", "judge_reason": "ok"}
        steps.append(ToolStep("settle", {}, True, settle))
    return JobRun("task-1-summarise", "summarise", steps)


def test_escrow_left_open_is_detected() -> None:
    assert left_in_escrow(job_with_hire(settled=False))
    assert not left_in_escrow(job_with_hire(settled=True))


def test_receipt_narration_uses_only_tool_results() -> None:
    text = receipt_narration(job_with_hire(settled=True))
    assert "pay-task-1-summarise was released" in text
    assert cited_ids(text) == ["task-1-summarise", "prov-summa", "pay-task-1-summarise"]


def test_memory_from_the_first_job_is_carried_to_the_next() -> None:
    recall = {
        "quarantines": [{"policy_id": "policy-1", "covered": ["prov-quickdigest"], "reason": "r"}],
        "lessons": [{"lesson_id": "lesson-1", "text": "Avoid the ring.", "source_ids": []}],
    }
    run = JobRun("t1-summarise", "summarise", [ToolStep("recall_memory", {}, True, recall)])
    note = remembered_note(run)
    assert "policy-1" in note and "Avoid the ring." in note
    assert remembered_note(JobRun("t1-x", "summarise")) == ""
