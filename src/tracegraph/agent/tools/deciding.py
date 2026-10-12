import time
from collections import Counter
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.agent.tools.lookups import load_job
from tracegraph.evidence.decisions import DecisionContext, record_decision
from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.evidence.scoring import ScoredCandidates, score_job_candidates
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.queries.catalogue import FIND_PROVIDERS
from tracegraph.trace.utility import ProviderScore


# Lists providers for a capability, leaving out quarantined ones
async def find_providers(session: AgentSession, capability: str) -> dict[str, Any]:
    timer = GraphTimer()
    rows = await session.database.rows(
        session.graph_name, FIND_PROVIDERS, {"capability": capability}, timer
    )
    return {"capability": capability, "providers": rows, "graph_ms": timer.total_ms}


# Scores every provider for a job with TRACE, records the decision, and returns who may be hired
async def trace_score(session: AgentSession, job_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    job = await load_job(session, job_id, timer)
    if job.status != "planned":
        raise ToolRefusedError(f"{job_id} is already {job.status}; it cannot be scored again")
    request = EvidenceRequest(
        session.graph_name,
        session.buyer_id,
        job.capability,
        time.time(),
        session.guard_rules,
        alone=session.view == "alone",
    )
    scored = await score_job_candidates(
        session.database,
        request,
        session.trace_settings,
        session.settings.scorer,
        session.tie_breaker,
    )
    decision_id = session.next_decision_id(job_id)
    context = DecisionContext(
        session.graph_name,
        decision_id,
        job_id,
        session.buyer_id,
        session.view,
        session.settings.guard_mode,
        time.time(),
    )
    await record_decision(session.database, context, scored, timer)
    summary = decision_summary(decision_id, scored, session.trace_settings.hireable_count)
    return {**summary, "graph_ms": round(scored.graph_ms + timer.total_ms, 2)}


# What the agent needs to see from a scored decision: the hireable few, their flags, the rest
def decision_summary(decision_id: str, scored: ScoredCandidates, hireable: int) -> dict[str, Any]:
    ranking = scored.ranking
    uncounted = uncounted_writers_by_provider(scored)
    return {
        "decision_id": decision_id,
        "status": ranking.status,
        "scorer": scored.scorer,
        "hireable": [
            hireable_entry(score, scored.prices, ranking.flags, uncounted)
            for score in ranking.ranked[:hireable]
        ],
        "other_eligible": len(ranking.ranked[hireable:]),
        "excluded": [
            {"provider_id": score.provider_id, "reason": score.excluded_because}
            for score in ranking.excluded
        ],
        "ignored_reports": sum(1 for report in scored.reports if not report.counted),
    }


# One hireable provider as the agent sees it
def hireable_entry(
    score: ProviderScore,
    prices: dict[str, int],
    flags: dict[str, list[str]],
    uncounted: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "provider_id": score.provider_id,
        "price_sats": prices.get(score.provider_id),
        "utility": round(score.utility, 4),
        "lcb": round(score.lcb, 3),
        "risk": round(score.risk, 3),
        "counted_successes": score.successes,
        "counted_failures": score.failures,
        "flags": flags.get(score.provider_id, []),
        "uncounted_writers": uncounted.get(score.provider_id, []),
    }


# The writers whose reports the guard ignored, most active first, up to five per provider
def uncounted_writers_by_provider(scored: ScoredCandidates) -> dict[str, list[str]]:
    counts: dict[str, Counter[str]] = {}
    for report in scored.reports:
        if not report.counted:
            counts.setdefault(report.provider_id, Counter())[report.writer_id] += 1
    return {
        provider: [
            writer for writer, _ in sorted(writers.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        ]
        for provider, writers in counts.items()
    }
