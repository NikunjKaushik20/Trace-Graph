from dataclasses import dataclass
from typing import Any

from tracegraph.evidence.reader import ReportRow
from tracegraph.evidence.scoring import ScoredCandidates
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.decisions import (
    LINK_COUNTED_JOBS,
    RECORD_DECISION,
    RECORD_EXCLUSIONS,
    RECORD_IGNORED_CLAIMS,
)
from tracegraph.trace.utility import ProviderScore


@dataclass(frozen=True)
class DecisionContext:
    graph_name: str
    decision_id: str
    job_id: str
    buyer_id: str
    view: str
    guard: str
    t: float


# Writes a scored decision into the graph: the ranking, exclusions, counted jobs and ignored claims
async def record_decision(
    database: GraphDatabase,
    context: DecisionContext,
    scored: ScoredCandidates,
    timer: GraphTimer | None = None,
) -> None:
    graph = context.graph_name
    links = {"decision_id": context.decision_id}
    excluded = [
        {"provider_id": score.provider_id, "reason": score.excluded_because}
        for score in scored.ranking.excluded
    ]
    job_ids = counted_job_ids(scored.reports)
    claims = [claim_row(report) for report in scored.reports if not report.counted]
    await database.run(graph, RECORD_DECISION, decision_params(context, scored), timer)
    await database.run(graph, RECORD_EXCLUSIONS, {**links, "excluded": excluded}, timer)
    await database.run(graph, LINK_COUNTED_JOBS, {**links, "job_ids": job_ids}, timer)
    await database.run(graph, RECORD_IGNORED_CLAIMS, {**links, "claims": claims}, timer)


# Properties of the Decision node and its RANKED edges
def decision_params(context: DecisionContext, scored: ScoredCandidates) -> dict[str, Any]:
    ranking = scored.ranking
    return {
        "job_id": context.job_id,
        "decision_id": context.decision_id,
        "buyer_id": context.buyer_id,
        "status": ranking.status,
        "flags": ranking.flag_lines,
        "scorer": scored.scorer,
        "view": context.view,
        "guard": context.guard,
        "graph_ms": scored.graph_ms,
        "t": context.t,
        "ranked": [ranked_row(position, score) for position, score in enumerate(ranking.ranked, 1)],
    }


# One RANKED edge's properties for a provider at a position
def ranked_row(position: int, score: ProviderScore) -> dict[str, Any]:
    return {
        "provider_id": score.provider_id,
        "position": position,
        "utility": score.utility,
        "lcb": score.lcb,
        "risk": score.risk,
        "ppr_distance": score.ppr_distance,
        "entropy": score.entropy,
        "sybil": score.sybil,
        "clique": score.clique,
    }


# Paid jobs behind the counted reports, each listed once
def counted_job_ids(reports: list[ReportRow]) -> list[str]:
    seen: dict[str, None] = {}
    for report in reports:
        if report.counted and report.job_id:
            seen[report.job_id] = None
    return list(seen)


# A refused report as a Claim row, with an id that stays the same across decisions
def claim_row(report: ReportRow) -> dict[str, Any]:
    claim_id = f"claim:{report.writer_id}:{report.provider_id}:{report.t:g}:{report.job_id or '-'}"
    return {
        "claim_id": claim_id,
        "writer_id": report.writer_id,
        "provider_id": report.provider_id,
        "reason": report.ignored_because,
        "ok": report.ok,
        "t": report.t,
        "job_id": report.job_id,
    }
