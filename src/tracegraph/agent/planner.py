from tracegraph.agent.prompts import PLANNER_SYSTEM
from tracegraph.llm.text_model import LlmUnavailableError, TextModel
from tracegraph.market.tasks import PlannedJob
from tracegraph.market.work import CAPABILITIES, Capability, parse_json_object

KEYWORDS: dict[Capability, tuple[str, ...]] = {
    "summarise": ("summar", "tl;dr", "digest"),
    "extract_keywords": ("keyword", "extract", "tags"),
    "translate": ("translat", "french"),
}


# Splits a task into jobs with the LLM, falling back to keyword matching if the reply is unusable
async def plan_jobs(model: TextModel, task_id: str, task_text: str) -> list[PlannedJob]:
    try:
        reply = await model.complete(PLANNER_SYSTEM, task_text, max_tokens=500)
    except LlmUnavailableError:
        reply = ""
    planned = jobs_from_reply(reply, task_id)
    return planned or jobs_from_keywords(task_id, task_text)


# Reads planned jobs from the planner's JSON, keeping only known capabilities, each once
def jobs_from_reply(reply: str, task_id: str) -> list[PlannedJob]:
    parsed = parse_json_object(reply)
    if parsed is None or not isinstance(parsed.get("jobs"), list):
        return []
    jobs: dict[Capability, PlannedJob] = {}
    for entry in parsed["jobs"]:
        if not isinstance(entry, dict) or len(jobs) == len(CAPABILITIES):
            continue
        capability = entry.get("capability")
        input_text = str(entry.get("input_text") or "").strip()
        if capability in CAPABILITIES and input_text and capability not in jobs:
            jobs[capability] = PlannedJob(f"{task_id}-{capability}", capability, input_text)
    return list(jobs.values())


# One job per capability named in the instructions, working on the text after the first colon
def jobs_from_keywords(task_id: str, task_text: str) -> list[PlannedJob]:
    head, _, body = task_text.partition(":")
    instructions = head.lower() if body.strip() else task_text.lower()
    input_text = body.strip() or task_text
    wanted = [
        capability
        for capability in CAPABILITIES
        if any(word in instructions for word in KEYWORDS[capability])
    ]
    return [
        PlannedJob(f"{task_id}-{capability}", capability, input_text)
        for capability in wanted or ["summarise"]
    ]
