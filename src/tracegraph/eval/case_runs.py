from dataclasses import dataclass, field
from typing import Literal

from tracegraph.agent.runs import JobRun

EvalLane = Literal["graph", "text"]


@dataclass
class CaseRun:
    case_id: str
    kind: str
    label: str
    lane: EvalLane
    hired: str | None = None
    hired_malicious: bool = False
    sats_to_scam: int = 0
    tool_path: list[str] = field(default_factory=list)
    investigated: bool = False
    quarantined: bool = False
    quarantine_backed: bool = True
    citations_passed: bool | None = None
    error: str | None = None


# What the graph agent did on one case, read from its tool steps
def graph_case_run(case_id: str, kind: str, label: str, job: JobRun) -> CaseRun:
    run = CaseRun(case_id, kind, label, "graph", tool_path=job.tool_path)
    seen: set[str] = set()
    for step in job.steps:
        if step.ok and step.name == "hire_with_escrow" and isinstance(step.result, dict):
            run.hired = str(step.result["provider_id"])
        if step.ok and step.name == "quarantine":
            run.quarantined = True
            run.quarantine_backed = run.quarantine_backed and {"funding_path", "find_ring"} <= seen
        if step.ok:
            seen.add(step.name)
    run.investigated = bool({"funding_path", "find_ring"} & set(job.tool_path))
    run.citations_passed = job.citations.passed and not job.citations.fell_back_to_receipt
    return run
