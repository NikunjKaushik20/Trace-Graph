import random

from tracegraph.llm.text_model import ScriptedModel
from tracegraph.market.paywall import MockLightning, PaymentRequired, authorization_header
from tracegraph.market.providers import HonestWork, ProviderAgent, ScamWork, StrategicWork
from tracegraph.market.work import Delivery, WorkOrder

ORDER = WorkOrder(
    "job-1", "summarise", "FalkorDB is a graph database built on sparse matrices.", 12
)
SUMMARY_MODEL = ScriptedModel(
    lambda system, prompt: '{"summary": "A graph database using sparse matrices."}'
)


async def test_first_request_gets_a_402_with_an_invoice_for_the_price() -> None:
    agent = ProviderAgent("prov-a", HonestWork(SUMMARY_MODEL), MockLightning())
    reply = await agent.handle(ORDER, authorization=None)
    assert isinstance(reply, PaymentRequired)
    assert reply.status_code == 402
    assert reply.invoice.amount_sats == 12
    assert reply.invoice.job_id == "job-1"


async def test_paying_the_invoice_unlocks_the_work() -> None:
    lightning = MockLightning()
    agent = ProviderAgent("prov-a", HonestWork(SUMMARY_MODEL), lightning)
    reply = await agent.handle(ORDER, authorization=None)
    assert isinstance(reply, PaymentRequired)
    preimage = lightning.pay(reply.invoice)
    delivery = await agent.handle(ORDER, authorization_header(reply.invoice.invoice_id, preimage))
    assert isinstance(delivery, Delivery)
    assert delivery.output == {"summary": "A graph database using sparse matrices."}


async def test_a_wrong_preimage_or_another_jobs_invoice_is_rejected() -> None:
    lightning = MockLightning()
    agent = ProviderAgent("prov-a", HonestWork(SUMMARY_MODEL), lightning)
    reply = await agent.handle(ORDER, authorization=None)
    assert isinstance(reply, PaymentRequired)
    forged = authorization_header(reply.invoice.invoice_id, "00" * 32)
    assert isinstance(await agent.handle(ORDER, forged), PaymentRequired)
    other = lightning.create_invoice("prov-a", "job-2", 12)
    stolen = authorization_header(other.invoice_id, lightning.pay(other))
    assert isinstance(await agent.handle(ORDER, stolen), PaymentRequired)
    assert isinstance(await agent.handle(ORDER, "Bearer nonsense"), PaymentRequired)


async def test_scam_work_ignores_the_input() -> None:
    first = await ScamWork().perform(ORDER)
    second = await ScamWork().perform(WorkOrder("job-2", "summarise", "Completely different.", 6))
    assert first == second


async def test_strategic_provider_walks_away_from_some_expensive_jobs_only() -> None:
    work = StrategicWork(HonestWork(SUMMARY_MODEL), random.Random(4))
    cheap = [await work.perform(WorkOrder(f"c{i}", "summarise", "text", 10)) for i in range(20)]
    expensive = [await work.perform(WorkOrder(f"e{i}", "summarise", "text", 15)) for i in range(20)]
    assert all(output is not None for output in cheap)
    assert 0 < sum(output is None for output in expensive) < 20
