import json
from typing import Any

from tracegraph.agent.prompts import MEMORY_NOTE
from tracegraph.agent.runs import JobRun, ToolStep


# A plain summary built from the tool results, used when the model's own summary cannot be trusted
def receipt_narration(job_run: JobRun) -> str:
    sentences = [f"Job {job_run.job_id} ({job_run.capability})."]
    for step in job_run.steps:
        sentence = step_sentence(step)
        if sentence:
            sentences.append(sentence)
    if len(sentences) == 1:
        sentences.append("No tool finished, so nothing was paid.")
    return " ".join(sentences)


# One sentence for a tool step that changed something or decided something
def step_sentence(step: ToolStep) -> str:
    if not step.ok or not isinstance(step.result, dict):
        return f"{step.name} was refused: {step.result}" if not step.ok else ""
    result = step.result
    if step.name == "trace_score":
        return f"Decision {result['decision_id']} was {result['status']}."
    if step.name == "find_ring" and result.get("is_ring"):
        return f"Found ring {result['ring_id']} funded through {result['hub_funder']}."
    if step.name == "quarantine":
        return f"Policy {result['policy_id']} quarantined {', '.join(result['covered'])}."
    if step.name == "hire_with_escrow":
        return f"Hired {result['provider_id']} with payment {result['payment_id']} held in escrow."
    if step.name == "settle":
        return f"Payment {result['payment_id']} was {result['status']}: {result['judge_reason']}."
    if step.name == "write_lesson":
        return f"Saved lesson {result['lesson_id']}."
    return ""


# What later jobs in the same task should know from the first job's recall_memory
def remembered_note(job_run: JobRun) -> str:
    for step in job_run.steps:
        if step.name == "recall_memory" and step.ok and isinstance(step.result, dict):
            memory = memory_digest(step.result)
            return MEMORY_NOTE.format(memory=json.dumps(memory, ensure_ascii=False)[:1500])
    return ""


# The parts of a recall worth carrying over: quarantines in force and lesson texts
def memory_digest(recall: dict[str, Any]) -> dict[str, Any]:
    return {
        "quarantines": [
            {"policy_id": policy["policy_id"], "covered": policy["covered"]}
            for policy in recall.get("quarantines", [])
        ],
        "lessons": [
            {"lesson_id": lesson["lesson_id"], "text": lesson["text"]}
            for lesson in recall.get("lessons", [])
        ],
    }


# True when money was put in escrow for this job and no settle went through after it
def left_in_escrow(job_run: JobRun) -> bool:
    held = False
    for step in job_run.steps:
        if step.ok and step.name == "hire_with_escrow":
            held = True
        if step.ok and step.name == "settle":
            held = False
    return held
