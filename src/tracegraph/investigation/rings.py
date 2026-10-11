import hashlib
from dataclasses import dataclass, field
from typing import Any

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.investigation import (
    FUNDING_BETWEENNESS,
    FUNDING_COMPONENT,
    FUNDING_PAGERANK,
    PRAISE_COMMUNITY,
    PRAISE_INSIDE,
)

ALGORITHMS = ["algo.WCC", "algo.labelPropagation", "algo.pageRank", "algo.betweenness"]


@dataclass(frozen=True)
class RingReport:
    provider_id: str
    ring_id: str | None
    providers: list[str]
    writers: list[str]
    wallets: list[str]
    outside_praise: int
    hub_id: str | None
    bridge_id: str | None
    praise_community: list[str]
    algorithms: list[str] = field(default_factory=lambda: list(ALGORITHMS))

    # True when the provider sits in a funding tree with outside writers who praised it
    @property
    def is_ring(self) -> bool:
        return self.ring_id is not None

    # Every node in the ring: providers, writers and wallets
    @property
    def member_ids(self) -> list[str]:
        return self.providers + self.writers + self.wallets


# Looks for a ring around a provider: shared funding (WCC), praise inside it, and who runs it
async def find_ring(
    database: GraphDatabase, graph_name: str, provider_id: str, timer: GraphTimer | None = None
) -> RingReport:
    target = {"provider_id": provider_id}
    component_rows = await database.rows(graph_name, FUNDING_COMPONENT, target, timer)
    members = list(component_rows[0]["members"] or []) if component_rows else []
    providers, writers, wallets = split_by_label(members)
    member_ids = {"member_ids": providers + writers + wallets}
    praise = await database.rows(graph_name, PRAISE_INSIDE, member_ids, timer)
    outside_praise = sum(int(row["reports"]) for row in praise if not row["admitted"])
    community_rows = await database.rows(graph_name, PRAISE_COMMUNITY, target, timer)
    community = list(community_rows[0]["community"] or []) if community_rows else []
    ranks = await database.rows(graph_name, FUNDING_PAGERANK, member_ids, timer)
    bridges = await database.rows(graph_name, FUNDING_BETWEENNESS, member_ids, timer)
    is_ring = outside_praise > 0 and len(providers + writers) > 1
    return RingReport(
        provider_id=provider_id,
        ring_id=ring_id_for(member_ids["member_ids"]) if is_ring else None,
        providers=providers,
        writers=writers,
        wallets=wallets,
        outside_praise=outside_praise,
        hub_id=top_wallet(ranks, wallets),
        bridge_id=top_wallet(bridges, wallets),
        praise_community=sorted(community),
    )


# Sorts component members into providers, writers and wallets
def split_by_label(members: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    providers, writers, wallets = [], [], []
    for member in members:
        labels = member["labels"]
        if "Provider" in labels:
            providers.append(str(member["id"]))
        elif "Wallet" in labels:
            wallets.append(str(member["id"]))
        else:
            writers.append(str(member["id"]))
    return sorted(providers), sorted(writers), sorted(wallets)


# The highest-scoring wallet in an algorithm's ordered results
def top_wallet(rows: list[dict[str, Any]], wallets: list[str]) -> str | None:
    for row in rows:
        if row["id"] in wallets:
            return str(row["id"])
    return None


# A stable id for a ring, from its sorted member ids
def ring_id_for(member_ids: list[str]) -> str:
    digest = hashlib.sha256("|".join(sorted(member_ids)).encode()).hexdigest()
    return f"ring-{digest[:10]}"
