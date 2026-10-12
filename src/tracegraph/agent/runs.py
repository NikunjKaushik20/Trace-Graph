import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from tracegraph.agent.citations import CitationCheck

TOOL_RESULT_LIMIT = 3000


@dataclass(frozen=True)
class AgentEvent:
    kind: str
    buyer_id: str
    job_id: str | None
    data: dict[str, Any]
    t: float = field(default_factory=time.time)


EventSink = Callable[[AgentEvent], Awaitable[None]]


@dataclass
class ToolStep:
    name: str
    arguments: dict[str, Any]
    ok: bool
    result: dict[str, Any] | str

    # Milliseconds FalkorDB spent on this tool's queries, when the tool reported it
    @property
    def graph_ms(self) -> float | None:
        if isinstance(self.result, dict) and "graph_ms" in self.result:
            return float(self.result["graph_ms"])
        return None

    # The result as the model sees it: compact JSON, cut to a fixed length
    def text_for_model(self) -> str:
        if isinstance(self.result, str):
            return self.result
        text = json.dumps(self.result, separators=(",", ":"), ensure_ascii=False, default=str)
        return text[:TOOL_RESULT_LIMIT]


@dataclass
class JobRun:
    job_id: str
    capability: str
    steps: list[ToolStep] = field(default_factory=list)
    narration: str = ""
    citations: CitationCheck = field(default_factory=CitationCheck)
    hit_step_cap: bool = False
    settled_by_safety_net: bool = False

    # The tools called, in order: the path the agent chose for this job
    @property
    def tool_path(self) -> list[str]:
        return [step.name for step in self.steps]


@dataclass
class TaskRun:
    task_id: str
    buyer_id: str
    task_text: str
    jobs: list[JobRun] = field(default_factory=list)


# An event sink that drops everything, for runs nobody is watching
async def ignore_event(event: AgentEvent) -> None:
    return None
