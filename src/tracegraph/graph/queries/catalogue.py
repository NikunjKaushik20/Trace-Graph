from tracegraph.graph.queries.query import Query

FIND_PROVIDERS = Query(
    name="find_providers",
    purpose="Providers offering a capability, with price, leaving out any a quarantine covers.",
    text="""
MATCH (provider:Provider {capability: $capability})
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WITH provider, count(policy) AS policies
WHERE policies = 0
RETURN provider.id AS provider_id, provider.name AS name, provider.price_sats AS price_sats
ORDER BY price_sats, provider_id
""",
)

BUYER_JOB = Query(
    name="buyer_job",
    purpose=(
        "One of this buyer's jobs: what it needs, its input, its status, and the latest "
        "decision made for it."
    ),
    text="""
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(task:Task)-[:SPLIT_INTO]->(job:Job {id: $job_id})
OPTIONAL MATCH (job)-[:FOR]->(provider:Provider)
OPTIONAL MATCH (job)-[:DECIDED_BY]->(decision:Decision)
WITH task, job, provider, decision
ORDER BY decision.created_at DESC
WITH task, job, provider, collect(decision.id) AS decision_ids
RETURN task.id AS task_id,
       job.capability AS capability,
       job.input_text AS input_text,
       job.status AS status,
       job.output_json AS output_json,
       job.delivery_note AS delivery_note,
       job.price_sats AS price_sats,
       provider.id AS provider_id,
       decision_ids
""",
)

PROVIDER_LISTING = Query(
    name="provider_listing",
    purpose="A provider's name and listed price in sats.",
    text="""
MATCH (provider:Provider {id: $provider_id})
RETURN provider.name AS name, provider.price_sats AS price_sats
""",
)

DECISION_OWNER = Query(
    name="decision_owner",
    purpose="Which buyer made a decision, so one buyer cannot act on another's decision.",
    text="""
MATCH (decision:Decision {id: $decision_id})
RETURN decision.buyer_id AS buyer_id
""",
)
