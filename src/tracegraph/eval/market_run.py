import random
from collections import Counter
from collections.abc import Awaitable, Callable

from tracegraph.eval.attackers import badmouth_jobs, praise_jobs
from tracegraph.eval.choosing import pick_greedy, provider_to_investigate, score_view
from tracegraph.eval.contract import Adversary, MarketContract
from tracegraph.eval.investigator import investigate
from tracegraph.eval.lanes import Lane
from tracegraph.eval.ledger import EvidenceLedger
from tracegraph.eval.outcomes import SeedResult, count_job, job_succeeds
from tracegraph.eval.population import build_market, write_market
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.names import eval_graph
from tracegraph.graph.queries.scoreboard import ROUND_REPORTS
from tracegraph.graph.schema import apply_schema
from tracegraph.market.graph_writes import record_settled_jobs
from tracegraph.market.records import SettledJob
from tracegraph.trace.settings import TraceSettings

RoundListener = Callable[[SeedResult], Awaitable[None]]


# A round listener for runs nobody is watching
async def ignore_round(result: SeedResult) -> None:
    return None


class MarketRun:
    # One lane on one seed: five buyers, sixty rounds, every decision read from FalkorDB
    def __init__(
        self,
        database: GraphDatabase,
        contract: MarketContract,
        lane: Lane,
        adversary: Adversary,
        seed: int,
        *,
        on_round: RoundListener = ignore_round,
        graph_tag: str = "",
    ) -> None:
        self.database = database
        self.on_round = on_round
        self.graph_tag = graph_tag
        self.contract = contract
        self.lane = lane
        self.adversary = adversary
        self.market = build_market(contract, seed, lane.funding_visible)
        self.settings = TraceSettings()
        self.tie_breaker = random.Random(f"{seed}:ties")
        self.attacker = random.Random(f"{seed}:attacker")
        self.result = SeedResult(lane.name, adversary, seed)
        self.jobs_done: Counter[str] = Counter()
        self.checked: set[str] = set()
        self.graph_of = {bid: self.graph_name(bid) for bid in self.market.buyer_ids}
        self.ledgers = {graph: self.new_ledger(graph) for graph in set(self.graph_of.values())}

    # Plays every round and always removes the lane's graphs afterwards
    async def play(self) -> SeedResult:
        try:
            await self.set_up()
            for round_index in range(self.contract.rounds):
                await self.play_round(round_index)
        finally:
            for graph in self.ledgers:
                await self.database.delete_graph(graph)
        return self.result

    # Creates the market graph, or one private graph per buyer in the Alone lane
    async def set_up(self) -> None:
        for graph in self.ledgers:
            await self.database.delete_graph(graph)
            await apply_schema(self.database, graph, embedding_dimensions=8)
            buyers = [bid for bid, name in self.graph_of.items() if name == graph]
            with_sybils = self.lane.attack != "none"
            await write_market(self.database, graph, self.market, buyers, with_sybils)

    # One round: read last round's reports, let attackers write, each buyer decides and pays
    async def play_round(self, round_index: int) -> None:
        timer = GraphTimer()
        jobs: dict[str, list[SettledJob]] = {graph: [] for graph in self.ledgers}
        for graph, ledger in self.ledgers.items():
            if round_index > 0:
                rows = await self.database.rows(
                    graph, ROUND_REPORTS, self.read_params(round_index - 1), timer
                )
                ledger.add_round(rows)
            ledger.advance_to(round_index)
            jobs[graph] += self.attack_jobs(ledger, round_index)
        for buyer_index, buyer_id in enumerate(self.market.buyer_ids):
            job = await self.buyer_turn(buyer_index, buyer_id, round_index, timer)
            if job is not None:
                jobs[self.graph_of[buyer_id]].append(job)
        for graph, batch in jobs.items():
            await record_settled_jobs(self.database, graph, batch, timer)
        self.result.round_ms.append(timer.total_ms)
        self.result.fraud_by_round.append(self.result.fraud_sats)
        await self.on_round(self.result)

    # One buyer scores its view, investigates if the lane allows, then hires the greedy pick
    async def buyer_turn(
        self, buyer_index: int, buyer_id: str, round_index: int, timer: GraphTimer
    ) -> SettledJob | None:
        graph = self.graph_of[buyer_id]
        ledger = self.ledgers[graph]
        scored = score_view(ledger.view_for(buyer_id), self.market.provider_ids, self.settings)
        suspect = provider_to_investigate(scored, self.settings, self.checked)
        if self.lane.quarantine and suspect is not None:
            self.checked.add(suspect)
            blocked = await investigate(
                self.database,
                graph,
                ledger,
                buyer_id=buyer_id,
                provider_id=suspect,
                round_index=round_index,
                timer=timer,
            )
            if blocked and self.result.quarantined_at_round is None:
                self.result.quarantined_at_round = round_index
            if blocked:
                scored = score_view(
                    ledger.view_for(buyer_id), self.market.provider_ids, self.settings
                )
        provider_id = pick_greedy(scored, self.tie_breaker)
        if provider_id is None:
            return None
        return self.hire(buyer_index, buyer_id, provider_id, round_index)

    # Runs the job with the pre-drawn price and outcome, and counts any fraud
    def hire(
        self, buyer_index: int, buyer_id: str, provider_id: str, round_index: int
    ) -> SettledJob:
        price = self.market.prices[round_index][buyer_index]
        draw = self.market.outcome_draws[round_index][buyer_index]
        done = self.jobs_done[provider_id]
        ok = job_succeeds(
            self.contract,
            self.market,
            self.adversary,
            provider_id=provider_id,
            price_sats=price,
            jobs_done=done,
            draw=draw,
        )
        self.jobs_done[provider_id] += 1
        count_job(self.result, self.market, provider_id, price, ok)
        job_id = f"j{round_index}-{buyer_id}"
        return SettledJob(job_id, f"pay-{job_id}", buyer_id, provider_id, price, ok, round_index)

    # The attacker's writes for this round, if the lane has an attacker
    def attack_jobs(self, ledger: EvidenceLedger, round_index: int) -> list[SettledJob]:
        if self.lane.attack == "praise":
            jobs = praise_jobs(self.contract, self.market, round_index, self.attacker)
        elif self.lane.attack == "badmouth":
            tally = ledger.buyer_tally
            jobs = badmouth_jobs(self.contract, self.market, round_index, tally, self.attacker)
        else:
            return []
        self.result.attacker_spend_sats += sum(job.price_sats for job in jobs)
        return jobs

    # Parameters for the round read: which round, and this lane's guard rules
    def read_params(self, round_index: int) -> dict[str, object]:
        return {"t": round_index, **self.lane.rules.as_query_params()}

    # The graph a buyer reads and writes: the shared one, or its own in the Alone lane
    def graph_name(self, buyer_id: str) -> str:
        lane_key = f"{self.lane.name}-{self.adversary}{self.graph_tag}"
        if self.lane.shared:
            return eval_graph(lane_key, self.result.seed)
        return eval_graph(lane_key, self.result.seed, buyer_id)

    # A ledger whose PageRank seeds are the buyers on that graph
    def new_ledger(self, graph: str) -> EvidenceLedger:
        buyers = [bid for bid, name in self.graph_of.items() if name == graph]
        return EvidenceLedger(seed_writers=buyers, delay_rounds=self.contract.delay_rounds)
