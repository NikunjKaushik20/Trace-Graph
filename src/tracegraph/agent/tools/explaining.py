from collections import Counter
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.evidence.rules import GuardMode
from tracegraph.evidence.what_if import what_if_decision
from tracegraph.evidence.what_if_text import what_if_sentence
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.queries.decisions import RECORD_DECISION
from tracegraph.graph.queries.evidence import CANDIDATE_EVIDENCE, TRACE_SCORES
from tracegraph.graph.queries.query import Query
from tracegraph.graph.queries.receipts import DECISION_RECEIPT, WHO_AUTHORISED


# The receipt for a decision: ranking, exclusions, counted evidence, ignored claims, investigation
async def explain_decision(session: AgentSession, decision_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    rows = await session.database.rows(
        session.graph_name, DECISION_RECEIPT, {"decision_id": decision_id}, timer
    )
    if not rows:
        raise ToolRefusedError(f"there is no decision {decision_id}")
    receipt = dict(rows[0])
    receipt["ignored"] = summarise_ignored(receipt["ignored"])
    receipt["queries"] = [query_note(query) for query in queries_behind(receipt["scorer"])]
    receipt["graph_ms"] = timer.total_ms
    return receipt


# Ignored claims grouped by provider and reason, with how many of each
def summarise_ignored(ignored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((claim["provider_id"], claim["reason"]) for claim in ignored)
    return [
        {"provider_id": provider_id, "reason": reason, "claims": count}
        for (provider_id, reason), count in sorted(counts.items())
    ]


# The Cypher that produced a decision, so the receipt can show it
def queries_behind(scorer: str | None) -> list[Query]:
    scoring_query = TRACE_SCORES if scorer == "udf" else CANDIDATE_EVIDENCE
    return [scoring_query, RECORD_DECISION]


# A query's name and purpose, for a receipt
def query_note(query: Query) -> dict[str, str]:
    return {"name": query.name, "purpose": query.purpose}


# Who authorised a payment: principal, buyer, task, job, decision and provider in one path
async def who_authorised(session: AgentSession, payment_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    rows = await session.database.rows(
        session.graph_name, WHO_AUTHORISED, {"payment_id": payment_id}, timer
    )
    if not rows:
        raise ToolRefusedError(f"there is no payment {payment_id} with an owning principal")
    return {**rows[0], "graph_ms": timer.total_ms}


# The same decision replayed as of its own time with a different guard, and what would change
async def what_if(
    session: AgentSession, decision_id: str, guard: GuardMode = "unguarded"
) -> dict[str, Any]:
    result = await what_if_decision(
        session.database, session.graph_name, decision_id, guard, session.trace_settings
    )
    if result is None:
        raise ToolRefusedError(f"there is no decision {decision_id}")
    return {**result.as_dict(), "summary": what_if_sentence(result)}
