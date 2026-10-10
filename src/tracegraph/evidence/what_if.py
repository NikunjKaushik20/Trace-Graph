import random
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.evidence.rules import GuardMode, GuardRules
from tracegraph.evidence.scoring import ScoredCandidates, ScorerName, score_job_candidates
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.what_if import PROVIDER_SINCE, RECORDED_DECISION
from tracegraph.trace.settings import TraceSettings


@dataclass(frozen=True)
class RecordedDecision:
    decision_id: str
    buyer_id: str
    capability: str
    view: str
    guard: GuardMode
    scorer: ScorerName
    t: float
    ranked_ids: list[str]


@dataclass
class ProviderShift:
    provider_id: str
    utility_before: float
    utility_after: float
    position_before: int | None
    position_after: int | None
    reports_counted_now: int
    writers: list[str]
    shared_funders: list[str]
    policies_since: list[str] = field(default_factory=list)
    released_since: int = 0
    failed_since: int = 0


@dataclass
class WhatIf:
    decision_id: str
    guard_used: str
    guard_tried: str
    top_used: str | None
    top_tried: str | None
    replay_matches_record: bool
    shifts: list[ProviderShift]
    graph_ms: float

    # True when the other guard would have put a different provider first
    @property
    def changed(self) -> bool:
        return self.top_used != self.top_tried

    # The result as plain JSON
    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "changed": self.changed}


# Replays a stored decision as of its own time, with the guard it used and with another one
async def what_if_decision(
    database: GraphDatabase,
    graph_name: str,
    decision_id: str,
    guard_tried: GuardMode,
    settings: TraceSettings,
) -> WhatIf | None:
    timer = GraphTimer()
    recorded = await load_recorded_decision(database, graph_name, decision_id, timer)
    if recorded is None:
        return None
    used = await rescore(database, graph_name, recorded, recorded.guard, settings)
    tried = await rescore(database, graph_name, recorded, guard_tried, settings)
    shifts = provider_shifts(used, tried)
    await add_what_happened_since(database, graph_name, recorded.t, shifts, timer)
    return WhatIf(
        decision_id=decision_id,
        guard_used=recorded.guard,
        guard_tried=guard_tried,
        top_used=top_id(used),
        top_tried=top_id(tried),
        replay_matches_record=ranked_ids(used) == recorded.ranked_ids,
        shifts=shifts,
        graph_ms=round(timer.total_ms + used.graph_ms + tried.graph_ms, 2),
    )


# The stored facts a replay needs, or None when there is no such decision
async def load_recorded_decision(
    database: GraphDatabase, graph_name: str, decision_id: str, timer: GraphTimer
) -> RecordedDecision | None:
    rows = await database.rows(graph_name, RECORDED_DECISION, {"decision_id": decision_id}, timer)
    if not rows:
        return None
    row = rows[0]
    return RecordedDecision(
        decision_id=decision_id,
        buyer_id=str(row["buyer_id"]),
        capability=str(row["capability"]),
        view=str(row["view"]),
        guard=cast(GuardMode, row["guard"]),
        scorer=cast(ScorerName, row["scorer"]),
        t=float(row["t"]),
        ranked_ids=[str(provider_id) for provider_id in row["ranked_ids"]],
    )


# Scores the decision's job again with only what the graph held at the decision's time
async def rescore(
    database: GraphDatabase,
    graph_name: str,
    recorded: RecordedDecision,
    guard: GuardMode,
    settings: TraceSettings,
) -> ScoredCandidates:
    request = EvidenceRequest(
        graph_name,
        recorded.buyer_id,
        recorded.capability,
        recorded.t,
        GuardRules.for_mode(guard),
        alone=recorded.view == "alone",
        as_of=recorded.t,
    )
    return await score_job_candidates(
        database, request, settings, recorded.scorer, random.Random(7)
    )


# The provider a scoring put first
def top_id(scored: ScoredCandidates) -> str | None:
    top = scored.ranking.top
    return top.provider_id if top else None


# Provider ids in ranked order
def ranked_ids(scored: ScoredCandidates) -> list[str]:
    return [score.provider_id for score in scored.ranking.ranked]


# Every provider whose score, place or counted reports differ between the two scorings
def provider_shifts(used: ScoredCandidates, tried: ScoredCandidates) -> list[ProviderShift]:
    utility_used = all_utilities(used)
    utility_tried = all_utilities(tried)
    shifts = []
    for provider_id in sorted(utility_used.keys() & utility_tried.keys()):
        shift = provider_shift(used, tried, provider_id)
        if shift.reports_counted_now or shift.position_before != shift.position_after:
            shifts.append(shift)
    return sorted(shifts, key=lambda shift: shift.utility_before - shift.utility_after)


# One provider's scores, places and newly counted reports under the two guards
def provider_shift(
    used: ScoredCandidates, tried: ScoredCandidates, provider_id: str
) -> ProviderShift:
    counted_before = {
        r.sort_key for r in used.reports if r.provider_id == provider_id and r.counted
    }
    newly_counted = [
        report
        for report in tried.reports
        if report.provider_id == provider_id
        and report.counted
        and report.sort_key not in counted_before
    ]
    return ProviderShift(
        provider_id=provider_id,
        utility_before=round(all_utilities(used)[provider_id], 4),
        utility_after=round(all_utilities(tried)[provider_id], 4),
        position_before=position_of(used, provider_id),
        position_after=position_of(tried, provider_id),
        reports_counted_now=len(newly_counted),
        writers=sorted({report.writer_id for report in newly_counted}),
        shared_funders=sorted({funder for r in newly_counted for funder in r.shared_funders}),
    )


# Utility for every scored provider, ranked or excluded
def all_utilities(scored: ScoredCandidates) -> dict[str, float]:
    scores = scored.ranking.ranked + scored.ranking.excluded
    return {score.provider_id: score.utility for score in scores}


# A provider's place in the ranking, from 1, or None when it was excluded
def position_of(scored: ScoredCandidates, provider_id: str) -> int | None:
    order = ranked_ids(scored)
    return order.index(provider_id) + 1 if provider_id in order else None


# Adds quarantines and payment outcomes that came after the decision, from the graph
async def add_what_happened_since(
    database: GraphDatabase,
    graph_name: str,
    since: float,
    shifts: list[ProviderShift],
    timer: GraphTimer,
) -> None:
    by_id = {shift.provider_id: shift for shift in shifts}
    params = {"provider_ids": list(by_id), "since": since}
    for row in await database.rows(graph_name, PROVIDER_SINCE, params, timer):
        shift = by_id[str(row["provider_id"])]
        shift.policies_since = [str(policy) for policy in row["policies_since"]]
        shift.released_since = int(row["released_since"])
        shift.failed_since = int(row["failed_since"])
