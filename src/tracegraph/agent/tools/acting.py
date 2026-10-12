import json
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.agent.tools.lookups import load_job, provider_listing
from tracegraph.graph.connection import GraphTimer
from tracegraph.market.escrow import HireRefusedError, HireRequest
from tracegraph.market.work import Delivery, WorkOrder


# Hires a provider from the job's latest decision: 402 handshake, escrow hold, work delivered
async def hire_with_escrow(session: AgentSession, job_id: str, provider_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    marketplace = session.require_marketplace()
    job = await load_job(session, job_id, timer)
    decision_id = job.latest_decision_id
    if decision_id is None:
        raise ToolRefusedError(f"call trace_score for {job_id} before hiring")
    provider_name, price = await provider_listing(session, provider_id, timer)
    order = WorkOrder(job_id, job.capability, job.input_text, price)
    hire = HireRequest(session.buyer_id, job_id, provider_id, decision_id)
    try:
        outcome = await marketplace.hire_with_escrow(hire, order, timer)
    except HireRefusedError as error:
        raise ToolRefusedError(str(error)) from error
    return {
        "job_id": job_id,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "decision_id": decision_id,
        "payment_id": outcome.payment.payment_id,
        "held_sats": outcome.payment.sats,
        "balance_sats": outcome.payment.balance_sats,
        "invoice_id": outcome.invoice.invoice_id,
        "delivered": outcome.delivery.delivered,
        "delivery_note": outcome.delivery.note,
        "output_preview": preview(outcome.delivery.output),
        "graph_ms": timer.total_ms,
    }


# Has the judge check the delivered work, then releases or refunds the escrow
async def settle(session: AgentSession, job_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    marketplace = session.require_marketplace()
    job = await load_job(session, job_id, timer)
    if job.status != "held" or job.price_sats is None or job.provider_id is None:
        raise ToolRefusedError(f"{job_id} has no payment held in escrow (status {job.status})")
    order = WorkOrder(job_id, job.capability, job.input_text, int(job.price_sats))
    delivery = Delivery(job_id, job.provider_id, job.output, job.delivery_note)
    outcome = await marketplace.settle(order, delivery, timer)
    return {
        "job_id": job_id,
        "provider_id": job.provider_id,
        "payment_id": outcome.payment.payment_id,
        "status": outcome.payment.status,
        "sats": outcome.payment.sats,
        "balance_sats": outcome.payment.balance_sats,
        "judge_stage": outcome.verdict.stage,
        "judge_reason": outcome.verdict.reason,
        "graph_ms": timer.total_ms,
    }


# The first 300 characters of a delivery, enough for the agent to see what came back
def preview(output: dict[str, Any] | None) -> str | None:
    if output is None:
        return None
    return json.dumps(output, ensure_ascii=False)[:300]
