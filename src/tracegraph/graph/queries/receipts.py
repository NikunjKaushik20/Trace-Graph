from tracegraph.graph.queries.query import Query

DECISION_RECEIPT = Query(
    name="decision_receipt",
    purpose=(
        "The receipt for a decision: how it ranked providers, whom it ruled out and why, how "
        "many paid jobs it counted, the claims it ignored, what was investigated, and the payment."
    ),
    text="""
MATCH (job:Job)-[:DECIDED_BY]->(decision:Decision {id: $decision_id})
OPTIONAL MATCH (decision)-[ranked:RANKED]->(candidate:Provider)
WITH job, decision, collect(CASE WHEN candidate IS NULL THEN null ELSE {
  provider_id: candidate.id, position: ranked.position, utility: ranked.utility,
  lcb: ranked.lcb, risk: ranked.risk, sybil: ranked.sybil, clique: ranked.clique
} END) AS ranked
OPTIONAL MATCH (decision)-[excluded:EXCLUDED]->(ruled_out:Provider)
WITH job, decision, ranked, collect(CASE WHEN ruled_out IS NULL THEN null ELSE {
  provider_id: ruled_out.id, reason: excluded.reason
} END) AS excluded
OPTIONAL MATCH (decision)-[:IGNORED]->(claim:Claim)-[:ABOUT]->(about:Provider)
WITH job, decision, ranked, excluded, collect(CASE WHEN claim IS NULL THEN null ELSE {
  provider_id: about.id, reason: claim.reason
} END) AS ignored
OPTIONAL MATCH (decision)-[:BASED_ON]->(counted:Job)
WITH job, decision, ranked, excluded, ignored, count(counted) AS counted_jobs
OPTIONAL MATCH (decision)-[trace:TRACED_FUNDING]->(traced:Provider)
WITH job, decision, ranked, excluded, ignored, counted_jobs, collect(CASE WHEN trace IS NULL
  THEN null ELSE {writer_id: trace.writer_id, provider_id: traced.id, node_ids: trace.node_ids,
  hops: trace.hops} END) AS funding_traces
OPTIONAL MATCH (decision)-[:INVESTIGATED]->(ring:Ring)
WITH job, decision, ranked, excluded, ignored, counted_jobs, funding_traces,
     collect(DISTINCT ring.id) AS rings
OPTIONAL MATCH (policy:Policy)-[:JUSTIFIED_BY]->(decision)
WITH job, decision, ranked, excluded, ignored, counted_jobs, funding_traces, rings,
     collect(policy.id) AS policies
OPTIONAL MATCH (payment:Payment)-[:FOR_DECISION]->(decision)
OPTIONAL MATCH (decision)-[:CHOSE]->(chosen:Provider)
RETURN decision.id AS decision_id, decision.buyer_id AS buyer_id, decision.status AS status,
       decision.flags AS flags, decision.scorer AS scorer, decision.view AS view,
       decision.guard AS guard, decision.graph_ms AS graph_ms, job.id AS job_id,
       job.capability AS capability, ranked, excluded, ignored, counted_jobs, funding_traces,
       rings, policies, chosen.id AS chosen_id, payment.id AS payment_id,
       payment.status AS payment_status, payment.sats AS sats,
       payment.verdict_reason AS verdict_reason
""",
)

WHO_AUTHORISED = Query(
    name="who_authorised",
    purpose=(
        "Who stands behind a payment: the principal that owns the buyer, the task, the job, "
        "the decision and the provider paid."
    ),
    text="""
MATCH (principal:Principal)-[:OWNS]->(buyer:Buyer)-[:MADE]->(payment:Payment {id: $payment_id})
MATCH (payment)-[:FOR_JOB]->(job:Job)<-[:SPLIT_INTO]-(task:Task)<-[:RECEIVED]-(buyer)
OPTIONAL MATCH (payment)-[:FOR_DECISION]->(decision:Decision)
OPTIONAL MATCH (job)-[:FOR]->(provider:Provider)
RETURN principal.id AS principal_id, principal.name AS principal_name, buyer.id AS buyer_id,
       task.id AS task_id, task.text AS task_text, job.id AS job_id,
       job.capability AS capability, decision.id AS decision_id, decision.status AS status,
       provider.id AS provider_id, payment.sats AS sats, payment.status AS payment_status
""",
)

KNOWN_IDS = Query(
    name="known_ids",
    purpose="Which of a list of ids exist as nodes, used to check every id the agent cites.",
    text="""
UNWIND $ids AS id
OPTIONAL MATCH (provider:Provider {id: id})
OPTIONAL MATCH (writer:Writer {id: id})
OPTIONAL MATCH (wallet:Wallet {id: id})
OPTIONAL MATCH (decision:Decision {id: id})
OPTIONAL MATCH (job:Job {id: id})
OPTIONAL MATCH (task:Task {id: id})
OPTIONAL MATCH (payment:Payment {id: id})
OPTIONAL MATCH (policy:Policy {id: id})
OPTIONAL MATCH (ring:Ring {id: id})
OPTIONAL MATCH (lesson:Lesson {id: id})
OPTIONAL MATCH (principal:Principal {id: id})
WITH id, coalesce(provider, writer, wallet, decision, job, task, payment, policy, ring, lesson,
                  principal) AS node
WHERE node IS NOT NULL
RETURN id
""",
)
