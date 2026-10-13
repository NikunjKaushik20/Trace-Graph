from dataclasses import dataclass

from tracegraph.eval.case_runs import CaseRun


@dataclass(frozen=True)
class LaneScore:
    lane: str
    cases: int
    scams_hired: int
    sats_to_scams: int
    rings_hired: int
    no_hire: int
    errors: int


@dataclass(frozen=True)
class ToolChoiceScore:
    ring_cases: int
    rings_investigated: int
    other_cases_investigated: int
    investigations: int
    precision: float
    recall: float
    quarantines: int
    quarantines_backed: int
    false_quarantines: int
    citation_pass_rate: float


# L1: scams hired and sats sent to them, for one lane
def lane_score(lane: str, runs: list[CaseRun]) -> LaneScore:
    return LaneScore(
        lane=lane,
        cases=len(runs),
        scams_hired=sum(run.hired_malicious for run in runs),
        sats_to_scams=sum(run.sats_to_scam for run in runs),
        rings_hired=sum(run.hired_malicious and run.label == "ring" for run in runs),
        no_hire=sum(run.hired is None for run in runs),
        errors=sum(run.error is not None for run in runs),
    )


# L2: does the graph agent investigate rings and leave clean cases alone, and are quarantines backed
def tool_choice_score(runs: list[CaseRun]) -> ToolChoiceScore:
    rings = [run for run in runs if run.label == "ring"]
    investigated = [run for run in runs if run.investigated]
    hits = sum(run.label == "ring" for run in investigated)
    quarantined = [run for run in runs if run.quarantined]
    checked = [run for run in runs if run.citations_passed is not None]
    return ToolChoiceScore(
        ring_cases=len(rings),
        rings_investigated=sum(run.investigated for run in rings),
        other_cases_investigated=len(investigated) - hits,
        investigations=len(investigated),
        precision=hits / len(investigated) if investigated else 0.0,
        recall=sum(run.investigated for run in rings) / len(rings) if rings else 0.0,
        quarantines=len(quarantined),
        quarantines_backed=sum(run.quarantine_backed for run in quarantined),
        false_quarantines=sum(run.label != "ring" for run in quarantined),
        citation_pass_rate=(
            sum(bool(run.citations_passed) for run in checked) / len(checked) if checked else 0.0
        ),
    )
