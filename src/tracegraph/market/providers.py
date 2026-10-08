import random
from typing import Any, Literal, Protocol

from tracegraph.llm.text_model import LlmUnavailableError, TextModel
from tracegraph.market.paywall import MockLightning, PaymentRequired
from tracegraph.market.work import INSTRUCTIONS, Capability, Delivery, WorkOrder, parse_json_object

Behaviour = Literal["honest", "scam", "strategic"]

SCAM_OUTPUTS: dict[Capability, dict[str, Any]] = {
    "summarise": {
        "summary": "This text covers many important topics in great detail. Highly recommended."
    },
    "extract_keywords": {"keywords": ["quality", "best", "recommended", "five stars"]},
    "translate": {"language": "fr", "text": "Bonjour. Merci beaucoup. Au revoir."},
}


class Work(Protocol):
    # Does the job, or returns None when the provider does not deliver
    async def perform(self, order: WorkOrder) -> dict[str, Any] | None: ...


class HonestWork:
    # Uses the given model to do the work
    def __init__(self, model: TextModel) -> None:
        self.model = model

    # Asks the LLM to do the task and returns its JSON answer
    async def perform(self, order: WorkOrder) -> dict[str, Any] | None:
        system = f"You are a careful worker paid per job. {INSTRUCTIONS[order.capability]}"
        try:
            reply = await self.model.complete(system, order.input_text, max_tokens=400)
        except LlmUnavailableError:
            return None
        return parse_json_object(reply)


class ScamWork:
    # Returns canned output that has the right shape but ignores the input
    async def perform(self, order: WorkOrder) -> dict[str, Any] | None:
        return dict(SCAM_OUTPUTS[order.capability])


class StrategicWork:
    # Wraps honest work and decides when to walk away from a job
    def __init__(self, honest: HonestWork, rng: random.Random, price_floor: int = 13) -> None:
        self.honest = honest
        self.rng = rng
        self.price_floor = price_floor

    # Works honestly on cheap jobs and walks away from half of the expensive ones
    async def perform(self, order: WorkOrder) -> dict[str, Any] | None:
        if order.price_sats >= self.price_floor and self.rng.random() < 0.5:
            return None
        return await self.honest.perform(order)


class ProviderAgent:
    # One provider behind a paywall, with the work it does once paid
    def __init__(self, provider_id: str, work: Work, lightning: MockLightning) -> None:
        self.provider_id = provider_id
        self.work = work
        self.lightning = lightning

    # Answers 402 with an invoice until the request carries proof of payment, then works
    async def handle(
        self, order: WorkOrder, authorization: str | None
    ) -> PaymentRequired | Delivery:
        paid = authorization is not None and self.lightning.proves_payment(
            authorization, self.provider_id, order.job_id
        )
        if not paid:
            invoice = self.lightning.create_invoice(
                self.provider_id, order.job_id, order.price_sats
            )
            return PaymentRequired(invoice)
        output = await self.work.perform(order)
        note = "" if output is not None else "provider did not deliver"
        return Delivery(order.job_id, self.provider_id, output, note)


# Picks the work a provider does from its scripted behaviour
def work_for(behaviour: Behaviour, model: TextModel, rng: random.Random) -> Work:
    if behaviour == "honest":
        return HonestWork(model)
    if behaviour == "strategic":
        return StrategicWork(HonestWork(model), rng)
    return ScamWork()
