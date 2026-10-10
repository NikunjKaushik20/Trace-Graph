from tracegraph.graph.queries.query import Query

RECORDED_DECISION = Query(
    name="recorded_decision",
    purpose=(
        "What a stored decision was made with: the job's capability, the buyer, view, guard, "
        "scorer and time, its ranking in order, and the provider it chose."
    ),
    text="""
MATCH (job:Job)-[:DECIDED_BY]->(decision:Decision {id: $decision_id})
OPTIONAL MATCH (decision)-[ranked:RANKED]->(provider:Provider)
WITH job, decision, ranked, provider ORDER BY ranked.position
WITH job, decision, collect(provider.id) AS ranked_ids
OPTIONAL MATCH (decision)-[:CHOSE]->(chosen:Provider)
RETURN decision.id AS decision_id, job.id AS job_id, decision.buyer_id AS buyer_id,
       job.capability AS capability, decision.view AS view, decision.guard AS guard,
       decision.scorer AS scorer, decision.created_at AS t, ranked_ids,
       chosen.id AS chosen_id
""",
)

PROVIDER_SINCE = Query(
    name="provider_since",
    purpose=(
        "What happened to some providers after a moment: quarantines that now cover them, and "
        "how their paid jobs ended."
    ),
    text="""
UNWIND $provider_ids AS provider_id
MATCH (provider:Provider {id: provider_id})
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WHERE policy.created_at > $since
WITH provider, collect(DISTINCT policy.id) AS policies_since
OPTIONAL MATCH (payment:Payment)-[:FOR_JOB]->(:Job)-[:FOR]->(provider)
WHERE payment.created_at > $since
RETURN provider.id AS provider_id, policies_since,
       sum(CASE WHEN payment.status = 'released' THEN 1 ELSE 0 END) AS released_since,
       sum(CASE WHEN payment.status IN ['refunded', 'defaulted'] THEN 1 ELSE 0 END)
         AS failed_since
""",
)
