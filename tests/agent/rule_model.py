import json
import re
from typing import Any

from tracegraph.llm.chat import ChatReply, Message, ToolCall

Call = tuple[str, dict[str, Any]]
Results = list[tuple[str, dict[str, Any]]]


class RuleFollowingModel:
    # Follows the buyer prompt's rules from the latest tool results; stands in for the LLM in tests
    def __init__(self) -> None:
        self.calls = 0

    # Picks the next tools the way the prompt tells the agent to, or writes the closing summary
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        results = tool_results(messages)
        brief = str(messages[1]["content"])
        next_calls = [] if tools is None else next_steps(brief, job_id_in(brief), results)
        if not next_calls:
            return ChatReply(closing_summary(results))
        tool_calls = []
        for name, arguments in next_calls:
            self.calls += 1
            tool_calls.append(ToolCall(f"call-{self.calls}", name, arguments))
        return ChatReply(None, tool_calls)

    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return ""


# The job id named in a job brief
def job_id_in(brief: str) -> str:
    found = re.search(r"Your job now: (\S+)", brief)
    return found.group(1) if found else ""


# The next tool calls, from what has happened so far in this job
def next_steps(brief: str, job_id: str, results: Results) -> list[Call]:
    names = [name for name, _ in results]
    if not names and "do not recall again" not in brief:
        return [("recall_memory", {"task_text": brief})]
    if "trace_score" not in names:
        return [("trace_score", {"job_id": job_id})]
    last_name, last = results[-1]
    decision = latest("trace_score", results)
    if last_name == "trace_score":
        return investigate_or_hire(job_id, decision)
    if last_name == "find_ring":
        return quarantine_or_rescore(job_id, decision, last)
    if last_name == "quarantine":
        return [("trace_score", {"job_id": job_id})]
    if last_name == "hire_with_escrow":
        return [("settle", {"job_id": job_id})]
    if last_name == "settle" and "quarantine" in names and "write_lesson" not in names:
        return [lesson_from(latest("quarantine", results))]
    return []


# Investigates the first flagged provider with uncounted writers in one turn, or hires the top pick
def investigate_or_hire(job_id: str, decision: dict[str, Any]) -> list[Call]:
    hireable = decision.get("hireable", [])
    if not hireable:
        return []
    for entry in hireable:
        if decision["status"] == "flagged" and entry["uncounted_writers"]:
            target = {"decision_id": decision["decision_id"], "provider_id": entry["provider_id"]}
            writer = {"writer_id": entry["uncounted_writers"][0]}
            return [("funding_path", {**target, **writer}), ("find_ring", target)]
    return [("hire_with_escrow", {"job_id": job_id, "provider_id": hireable[0]["provider_id"]})]


# Quarantines a ring that was found, or scores again when there was none
def quarantine_or_rescore(
    job_id: str, decision: dict[str, Any], ring: dict[str, Any]
) -> list[Call]:
    if not ring.get("is_ring"):
        return [
            (
                "hire_with_escrow",
                {"job_id": job_id, "provider_id": decision["hireable"][0]["provider_id"]},
            )
        ]
    reason = f"Praise for {ring['provider_id']} is paid for through {ring['hub_funder']}."
    arguments = {
        "decision_id": decision["decision_id"],
        "ring_id": ring["ring_id"],
        "reason": reason,
    }
    return [("quarantine", arguments)]


# A lesson citing the quarantine and the decision behind it
def lesson_from(policy: dict[str, Any]) -> Call:
    text = "A cheap provider praised only by uncounted writers was a funded ring."
    return (
        "write_lesson",
        {"text": text, "evidence_ids": [policy["decision_id"], policy["policy_id"]]},
    )


# Every successful tool result in the conversation, in order, with its tool name
def tool_results(messages: list[Message]) -> Results:
    names = {
        call["id"]: call["function"]["name"]
        for message in messages
        for call in message.get("tool_calls") or []
    }
    return [
        (names[message["tool_call_id"]], json.loads(message["content"]))
        for message in messages
        if message["role"] == "tool" and message["content"].startswith("{")
    ]


# The newest result of a given tool
def latest(name: str, results: Results) -> dict[str, Any]:
    return next(result for tool, result in reversed(results) if tool == name)


# A short summary that cites only ids that came back from the tools
def closing_summary(results: Results) -> str:
    sentences = []
    for name, result in results:
        if name == "trace_score":
            sentences.append(f"Decision {result['decision_id']} was {result['status']}.")
        if name == "settle":
            paid = f"Payment {result['payment_id']} to {result['provider_id']}"
            sentences.append(f"{paid} was {result['status']}.")
    return " ".join(sentences) or "Nothing was paid."
