import time
from dataclasses import dataclass

from tracegraph.graph.connection import GraphTimer
from tracegraph.llm.text_model import TextModel
from tracegraph.market.escrow import (
    Escrow,
    HeldPayment,
    HireRefusedError,
    HireRequest,
    SettledPayment,
)
from tracegraph.market.judge import Verdict, judge_delivery
from tracegraph.market.paywall import Invoice, MockLightning, PaymentRequired, authorization_header
from tracegraph.market.providers import ProviderAgent
from tracegraph.market.work import Delivery, WorkOrder


@dataclass(frozen=True)
class HireOutcome:
    invoice: Invoice
    payment: HeldPayment
    delivery: Delivery


@dataclass(frozen=True)
class SettleOutcome:
    verdict: Verdict
    payment: SettledPayment


class Marketplace:
    # Holds what a hire needs: escrow, the payment network, provider agents and the judge
    def __init__(
        self,
        escrow: Escrow,
        lightning: MockLightning,
        providers: dict[str, ProviderAgent],
        judge_model: TextModel,
    ) -> None:
        self.escrow = escrow
        self.lightning = lightning
        self.providers = providers
        self.judge_model = judge_model

    # Runs the 402 handshake: ask, get an invoice, hold the money in escrow, pay, collect the work
    async def hire_with_escrow(
        self, hire: HireRequest, order: WorkOrder, timer: GraphTimer | None = None
    ) -> HireOutcome:
        provider = self.providers.get(hire.provider_id)
        if provider is None:
            raise HireRefusedError(f"no provider agent is running for {hire.provider_id}")
        first_reply = await provider.handle(order, authorization=None)
        if not isinstance(first_reply, PaymentRequired):
            raise HireRefusedError("provider answered without asking for payment")
        invoice = first_reply.invoice
        payment = await self.escrow.hold(hire, invoice, time.time(), timer)
        preimage = self.lightning.pay(invoice)
        header = authorization_header(invoice.invoice_id, preimage)
        delivery = as_delivery(await provider.handle(order, header), order, hire.provider_id)
        await self.escrow.record_delivery(delivery, time.time(), timer)
        return HireOutcome(invoice, payment, delivery)

    # Has the judge rule on the delivery, then releases or refunds the escrow
    async def settle(
        self, order: WorkOrder, delivery: Delivery, timer: GraphTimer | None = None
    ) -> SettleOutcome:
        verdict = await judge_delivery(order, delivery, self.judge_model)
        payment = await self.escrow.settle(order.job_id, verdict, time.time(), timer)
        return SettleOutcome(verdict, payment)


# A provider that still asks for payment after being paid has delivered nothing
def as_delivery(reply: PaymentRequired | Delivery, order: WorkOrder, provider_id: str) -> Delivery:
    if isinstance(reply, PaymentRequired):
        return Delivery(order.job_id, provider_id, None, "provider rejected the payment proof")
    return reply
