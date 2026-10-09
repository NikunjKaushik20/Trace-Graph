import json
from dataclasses import dataclass

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.jobs import HIRE_CHECK, HOLD_PAYMENT, RECORD_DELIVERY, SETTLE_PAYMENT
from tracegraph.market.judge import Verdict
from tracegraph.market.paywall import Invoice
from tracegraph.market.work import Delivery


class HireRefusedError(RuntimeError):
    pass


@dataclass(frozen=True)
class HireRequest:
    buyer_id: str
    job_id: str
    provider_id: str
    decision_id: str


@dataclass(frozen=True)
class HeldPayment:
    payment_id: str
    sats: int
    balance_sats: int


@dataclass(frozen=True)
class SettledPayment:
    payment_id: str
    status: str
    sats: int
    balance_sats: int
    provider_id: str


class Escrow:
    # Works on one market graph and allows hires from the top few of a decision
    def __init__(self, database: GraphDatabase, graph_name: str, hireable_count: int = 3) -> None:
        self.database = database
        self.graph_name = graph_name
        self.hireable_count = hireable_count

    # Explains why a hire is not allowed, or returns None when it is
    async def refusal_reason(
        self, hire: HireRequest, invoice: Invoice, timer: GraphTimer | None = None
    ) -> str | None:
        rows = await self.database.rows(self.graph_name, HIRE_CHECK, hire_params(hire), timer)
        if not rows:
            return "job or provider not found for this buyer"
        check = rows[0]
        if check["position"] is None or check["position"] > self.hireable_count:
            return f"provider is not in the top {self.hireable_count} of this decision"
        if check["policies"]:
            return f"provider is quarantined by {', '.join(check['policies'])}"
        if check["job_status"] != "planned":
            return f"job is already {check['job_status']}"
        listed = check["price_sats"]
        if invoice.amount_sats != listed:
            return f"invoice asks {invoice.amount_sats} sats but the listed price is {listed}"
        if check["balance_sats"] < invoice.amount_sats:
            return "buyer cannot afford this job"
        return None

    # Takes the price from the buyer and holds it against the job until the judge rules
    async def hold(
        self, hire: HireRequest, invoice: Invoice, t: float, timer: GraphTimer | None = None
    ) -> HeldPayment:
        reason = await self.refusal_reason(hire, invoice, timer)
        if reason is not None:
            raise HireRefusedError(reason)
        params = {
            **hire_params(hire),
            "sats": invoice.amount_sats,
            "payment_id": f"pay-{hire.job_id}",
            "invoice_id": invoice.invoice_id,
            "payment_hash": invoice.payment_hash,
            "hireable_count": self.hireable_count,
            "t": t,
        }
        rows = await self.database.rows(self.graph_name, HOLD_PAYMENT, params, timer)
        if not rows:
            raise HireRefusedError("the graph refused the hold")
        return HeldPayment(
            str(rows[0]["payment_id"]), invoice.amount_sats, int(rows[0]["balance_sats"])
        )

    # Stores the provider's delivery on the job
    async def record_delivery(
        self, delivery: Delivery, t: float, timer: GraphTimer | None = None
    ) -> None:
        params = {
            "job_id": delivery.job_id,
            "output_json": json.dumps(delivery.output) if delivery.output is not None else None,
            "note": delivery.note,
            "t": t,
        }
        await self.database.run(self.graph_name, RECORD_DELIVERY, params, timer)

    # Releases or refunds the held payment by the judge's verdict and records the outcome
    async def settle(
        self, job_id: str, verdict: Verdict, t: float, timer: GraphTimer | None = None
    ) -> SettledPayment:
        params = {
            "job_id": job_id,
            "ok": verdict.passed,
            "stage": verdict.stage,
            "reason": verdict.reason,
            "t": t,
        }
        rows = await self.database.rows(self.graph_name, SETTLE_PAYMENT, params, timer)
        if not rows:
            raise HireRefusedError(f"no held payment for job {job_id}")
        row = rows[0]
        return SettledPayment(
            str(row["payment_id"]),
            str(row["status"]),
            int(row["sats"]),
            int(row["balance_sats"]),
            str(row["provider_id"]),
        )


# The ids every hiring query takes
def hire_params(hire: HireRequest) -> dict[str, str]:
    return {
        "buyer_id": hire.buyer_id,
        "job_id": hire.job_id,
        "provider_id": hire.provider_id,
        "decision_id": hire.decision_id,
    }
