from tracegraph.graph.queries.query import Query

TASK_IDS = Query(
    name="task_ids",
    purpose="Every task id in the graph, so a restarted server never hands out one already used.",
    text="""
MATCH (task:Task)
RETURN task.id AS task_id
""",
)

OPEN_TASK = Query(
    name="open_task",
    purpose="A buyer receives a task and splits it into planned jobs, one per capability.",
    read_only=False,
    text="""
MATCH (buyer:Buyer {id: $buyer_id})
CREATE (buyer)-[:RECEIVED]->(task:Task {id: $task_id, text: $text, created_at: $t})
WITH task
UNWIND $jobs AS row
CREATE (task)-[:SPLIT_INTO]->(:Job {
  id: row.job_id,
  capability: row.capability,
  input_text: row.input_text,
  status: 'planned',
  created_at: $t
})
""",
)

HIRE_CHECK = Query(
    name="hire_check",
    purpose=(
        "Before paying: is the provider in the top 3 of this job's decision, not quarantined, "
        "is the job still planned, and can the buyer afford it?"
    ),
    text="""
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(:Task)-[:SPLIT_INTO]->(job:Job {id: $job_id})
MATCH (provider:Provider {id: $provider_id})
OPTIONAL MATCH (job)-[:DECIDED_BY]->(:Decision {id: $decision_id})-[ranked:RANKED]->(provider)
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
RETURN job.status AS job_status,
       buyer.balance_sats AS balance_sats,
       provider.price_sats AS price_sats,
       ranked.position AS position,
       collect(policy.id) AS policies
""",
)

HOLD_PAYMENT = Query(
    name="hold_payment",
    purpose=(
        "Escrow hold: takes the price from the buyer's balance and records a held Payment for "
        "the job, the provider and the decision. Re-checks the hiring rules in the same query."
    ),
    read_only=False,
    text="""
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(:Task)-[:SPLIT_INTO]->(job:Job {id: $job_id})
MATCH (job)-[:DECIDED_BY]->(decision:Decision {id: $decision_id})
      -[ranked:RANKED]->(provider:Provider {id: $provider_id})
WHERE ranked.position <= $hireable_count AND job.status = 'planned' AND buyer.balance_sats >= $sats
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WITH buyer, job, decision, provider, count(policy) AS policies
WHERE policies = 0
SET buyer.balance_sats = buyer.balance_sats - $sats,
    job.status = 'held',
    job.price_sats = $sats
CREATE (job)-[:FOR]->(provider)
CREATE (decision)-[:CHOSE]->(provider)
CREATE (buyer)-[:MADE]->(payment:Payment {
  id: $payment_id,
  sats: $sats,
  status: 'held',
  invoice_id: $invoice_id,
  payment_hash: $payment_hash,
  created_at: $t
})-[:FOR_JOB]->(job)
CREATE (payment)-[:FOR_DECISION]->(decision)
RETURN payment.id AS payment_id, buyer.balance_sats AS balance_sats
""",
)

RECORD_DELIVERY = Query(
    name="record_delivery",
    purpose="Stores what the provider sent back for a job, or that it sent nothing.",
    read_only=False,
    text="""
MATCH (job:Job {id: $job_id})
SET job.output_json = $output_json, job.delivery_note = $note, job.delivered_at = $t
""",
)

SETTLE_PAYMENT = Query(
    name="settle_payment",
    purpose=(
        "Escrow settle: releases the held payment to the provider on a pass, refunds the buyer "
        "on a fail, and writes the buyer's REPORTED outcome edge."
    ),
    read_only=False,
    text="""
MATCH (buyer:Buyer)-[:MADE]->(payment:Payment {status: 'held'})-[:FOR_JOB]->(job:Job {id: $job_id})
MATCH (job)-[:FOR]->(provider:Provider)
SET payment.status = CASE WHEN $ok THEN 'released' ELSE 'refunded' END,
    payment.settled_at = $t,
    payment.verdict_stage = $stage,
    payment.verdict_reason = $reason,
    job.status = CASE WHEN $ok THEN 'done' ELSE 'failed' END,
    buyer.balance_sats = buyer.balance_sats + CASE WHEN $ok THEN 0 ELSE payment.sats END,
    provider.earned_sats = coalesce(provider.earned_sats, 0)
                           + CASE WHEN $ok THEN payment.sats ELSE 0 END
CREATE (buyer)-[:REPORTED {ok: $ok, t: $t, job_id: job.id}]->(provider)
RETURN payment.id AS payment_id,
       payment.status AS status,
       payment.sats AS sats,
       buyer.balance_sats AS balance_sats,
       provider.id AS provider_id
""",
)
