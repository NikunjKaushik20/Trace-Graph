from tracegraph.graph.queries.query import Query

CREATE_PROVIDERS = Query(
    name="create_providers",
    purpose="Adds providers with their capability and price.",
    read_only=False,
    text="""
UNWIND $providers AS row
MERGE (provider:Provider {id: row.id})
SET provider.name = row.name,
    provider.capability = row.capability,
    provider.price_sats = row.price_sats
""",
)

CREATE_BUYERS = Query(
    name="create_buyers",
    purpose="Adds buyer agents, whether they are admitted, and their starting balance.",
    read_only=False,
    text="""
UNWIND $buyers AS row
MERGE (buyer:Writer:Buyer {id: row.id})
SET buyer.name = row.name,
    buyer.admitted = row.admitted,
    buyer.balance_sats = row.balance_sats
WITH buyer, row
WHERE row.principal_id IS NOT NULL
MERGE (principal:Principal {id: row.principal_id})
SET principal.name = row.principal_name
MERGE (principal)-[:OWNS]->(buyer)
""",
)

CREATE_WRITERS = Query(
    name="create_writers",
    purpose="Adds outside identities that can write reports but are not buyers.",
    read_only=False,
    text="""
UNWIND $writers AS row
MERGE (:Writer {id: row.id})
""",
)

CREATE_WALLETS = Query(
    name="create_wallets",
    purpose="Adds intermediate wallets that pass funds along a funding chain.",
    read_only=False,
    text="""
UNWIND $wallet_ids AS wallet_id
MERGE (:Wallet {id: wallet_id})
""",
)

CREATE_ROOTS = Query(
    name="create_roots",
    purpose="Adds funding roots: the wallets where a funding chain starts.",
    read_only=False,
    text="""
UNWIND $root_ids AS root_id
MERGE (:Wallet:Root {id: root_id})
""",
)

LINK_FUNDING = Query(
    name="link_funding",
    purpose="Adds FUNDED_BY links from buyers, writers, providers and wallets to their funder.",
    read_only=False,
    text="""
UNWIND $links AS link
OPTIONAL MATCH (writer:Writer {id: link.funded_id})
OPTIONAL MATCH (provider:Provider {id: link.funded_id})
OPTIONAL MATCH (wallet:Wallet {id: link.funded_id})
WITH link, coalesce(writer, provider, wallet) AS funded
WHERE funded IS NOT NULL
MATCH (funder:Wallet {id: link.funder_id})
MERGE (funded)-[:FUNDED_BY]->(funder)
""",
)
