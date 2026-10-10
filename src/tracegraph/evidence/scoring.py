import random
from dataclasses import asdict, dataclass
from typing import Any, Literal

from tracegraph.evidence.reader import (
    EvidenceRequest,
    ReportRow,
    prices_from,
    read_candidate_evidence,
    report_from_row,
)
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.evidence import TRACE_SCORES
from tracegraph.graph.udf_loader import rows_with_trace_udf
from tracegraph.trace.ranking import Ranking, order_scores, score_candidates
from tracegraph.trace.settings import TraceSettings
from tracegraph.trace.utility import ProviderScore

ScorerName = Literal["udf", "python"]


@dataclass
class ScoredCandidates:
    ranking: Ranking
    reports: list[ReportRow]
    prices: dict[str, int]
    scorer: ScorerName
    graph_ms: float


# Scores every candidate for a buyer's job and ranks them, in FalkorDB or in Python
async def score_job_candidates(
    database: GraphDatabase,
    request: EvidenceRequest,
    settings: TraceSettings,
    scorer: ScorerName,
    tie_breaker: random.Random,
) -> ScoredCandidates:
    timer = GraphTimer()
    if scorer == "udf":
        scores, reports, prices = await score_in_database(database, request, settings, timer)
    else:
        scores, reports, prices = await score_in_python(database, request, settings, timer)
    ranking = order_scores(scores, settings, tie_breaker)
    return ScoredCandidates(ranking, reports, prices, scorer, timer.total_ms)


# Runs the guard and the TRACE utility inside FalkorDB with the Trace UDF
async def score_in_database(
    database: GraphDatabase, request: EvidenceRequest, settings: TraceSettings, timer: GraphTimer
) -> tuple[list[ProviderScore], list[ReportRow], dict[str, int]]:
    params = {**request.as_query_params(), "settings": asdict(settings)}
    rows = await rows_with_trace_udf(database, request.graph_name, TRACE_SCORES, params, timer)
    row = rows[0] if rows else {}
    scores = [score_from_udf(score) for score in row.get("scores") or []]
    reports = sorted(
        (report_from_row(report) for report in row.get("reports") or []),
        key=lambda report: report.sort_key,
    )
    return scores, reports, prices_from(row.get("providers") or [])


# Reads the evidence from FalkorDB and runs the Python copy of TRACE on it
async def score_in_python(
    database: GraphDatabase, request: EvidenceRequest, settings: TraceSettings, timer: GraphTimer
) -> tuple[list[ProviderScore], list[ReportRow], dict[str, int]]:
    candidates = await read_candidate_evidence(database, request, timer)
    scores = score_candidates(
        candidates.evidence_by_provider,
        candidates.success_edges,
        candidates.seed_writers,
        settings,
    )
    return scores, candidates.reports, candidates.prices


# Turns one score map returned by the UDF into a ProviderScore
def score_from_udf(row: dict[str, Any]) -> ProviderScore:
    return ProviderScore(
        provider_id=str(row["provider_id"]),
        utility=float(row["utility"]),
        lcb=float(row["lcb"]),
        risk=float(row["risk"]),
        ppr_distance=float(row["ppr_distance"]),
        entropy=float(row["entropy"]),
        capability=float(row["capability"]),
        sybil=float(row["sybil"]),
        clique=float(row["clique"]),
        cusum=float(row["cusum"]),
        successes=int(row["successes"]),
        failures=int(row["failures"]),
        ignored_claims=int(row["ignored_claims"]),
        excluded_because=row["excluded_because"],
    )
