from tracegraph.graph.queries.query import Query

JOB_STORY = Query(
    name="job_story",
    purpose=(
        "One job from task to outcome: who asked for it, the decisions made for it, the provider "
        "hired, the payment and how it ended, and the judge's reason."
    ),
    text="""
MATCH (buyer:Buyer)-[:RECEIVED]->(task:Task)-[:SPLIT_INTO]->(job:Job {id: $job_id})
OPTIONAL MATCH (job)-[:DECIDED_BY]->(decision:Decision)
WITH buyer, task, job, decision ORDER BY decision.created_at
WITH buyer, task, job, collect(decision.id) AS decision_ids
OPTIONAL MATCH (job)-[:FOR]->(provider:Provider)
OPTIONAL MATCH (payment:Payment)-[:FOR_JOB]->(job)
RETURN buyer.id AS buyer_id, task.id AS task_id, task.text AS task_text,
       job.id AS job_id, job.capability AS capability, job.status AS job_status,
       decision_ids, provider.id AS provider_id,
       payment.id AS payment_id, payment.status AS payment_status,
       payment.sats AS sats, payment.verdict_reason AS judge_reason
""",
)

RECENT_JOBS = Query(
    name="recent_jobs",
    purpose=(
        "The newest jobs in the market with their provider and how the payment ended, "
        "optionally only released or refunded ones: how the investigator finds 'job 14'."
    ),
    text="""
MATCH (buyer:Buyer)-[:RECEIVED]->(task:Task)-[:SPLIT_INTO]->(job:Job)
OPTIONAL MATCH (job)-[:FOR]->(provider:Provider)
OPTIONAL MATCH (payment:Payment)-[:FOR_JOB]->(job)
WITH buyer, task, job, provider, payment
WHERE $payment_status IS NULL OR payment.status = $payment_status
RETURN buyer.id AS buyer_id, task.id AS task_id, job.id AS job_id,
       job.capability AS capability, provider.id AS provider_id,
       payment.id AS payment_id, payment.status AS payment_status
ORDER BY job.created_at DESC
LIMIT $limit
""",
)

FUNDING_CHAIN = Query(
    name="funding_chain",
    purpose=(
        "Who funds a node, up to 3 FUNDED_BY hops, and who else draws on the same funders: "
        "the money behind a writer or a provider."
    ),
    text="""
MATCH (start {id: $node_id})
OPTIONAL MATCH chain = (start)-[:FUNDED_BY*1..3]->(funder)
WITH start, collect(DISTINCT [node IN nodes(chain) | node.id]) AS chains,
     collect(DISTINCT funder) AS funders
UNWIND (CASE WHEN size(funders) = 0 THEN [null] ELSE funders END) AS funder
OPTIONAL MATCH (other)-[:FUNDED_BY*1..3]->(funder)
WHERE other <> start AND NOT other:Wallet
WITH start, chains, funder, collect(DISTINCT other.id) AS also_funded
RETURN start.id AS node_id, labels(start) AS labels, chains,
       collect(CASE WHEN funder IS NULL THEN null ELSE {funder_id: funder.id,
                also_funds: also_funded} END) AS shared_funders
""",
)

NEIGHBOURHOOD = Query(
    name="neighbourhood",
    purpose="Every node within one or two hops of a node, with the edges between them.",
    text="""
MATCH (start {id: $node_id})
OPTIONAL MATCH path = (start)-[*1..2]-(other)
WHERE length(path) <= $hops
WITH start, collect(path)[..$limit] AS paths
UNWIND (CASE WHEN size(paths) = 0 THEN [null] ELSE paths END) AS path
UNWIND (CASE WHEN path IS NULL THEN [null] ELSE relationships(path) END) AS edge
WITH start, collect(DISTINCT edge) AS edges
WITH start, edges,
     [edge IN edges | startNode(edge)] + [edge IN edges | endNode(edge)] + [start] AS touched
UNWIND touched AS node
WITH edges, collect(DISTINCT node) AS nodes
RETURN [node IN nodes | {id: node.id, labels: labels(node), name: node.name,
        status: node.status}] AS nodes,
       [edge IN edges | {source: startNode(edge).id, target: endNode(edge).id,
        type: type(edge)}] AS edges
""",
)

GRAPH_SNAPSHOT = Query(
    name="graph_snapshot",
    purpose=(
        "The market as the graph view draws it: every node except stored embeddings, and every "
        "edge between them, capped for the browser."
    ),
    text="""
MATCH (source)-[edge]->(target)
WHERE NOT source:Lesson AND NOT target:Lesson
WITH source, edge, target LIMIT $limit
WITH collect(DISTINCT source) + collect(DISTINCT target) AS ends,
     collect({source: source.id, target: target.id, type: type(edge)}) AS edges
UNWIND ends AS node
WITH edges, collect(DISTINCT node) AS nodes
RETURN [node IN nodes | {id: node.id, labels: labels(node), name: node.name,
        status: node.status}] AS nodes,
       edges
""",
)
