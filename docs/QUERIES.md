# Cypher queries

Every query the backend sends to FalkorDB, generated from the `Query` objects in
`src/tracegraph/graph/queries/` by `tools/write_queries_doc.py`. The quality gate fails if this
file is out of date. Read-only queries run with `GRAPH.RO_QUERY`.

Graph algorithms used: `algo.SPpaths` (funding path), `algo.WCC` (funding components),
`algo.labelPropagation` (CDLP communities), `algo.pageRank` (funding hubs), `algo.betweenness`
(brokers), and the vector index `db.idx.vector.queryNodes` (memory recall). TRACE scoring runs
inside FalkorDB as the JavaScript UDF library in `src/tracegraph/graph/udf/trace_score.js`,
called from `trace_scores` below.

## Writing the market

### `create_providers` (writes)

Adds providers with their capability and price.

```cypher
UNWIND $providers AS row
MERGE (provider:Provider {id: row.id})
SET provider.name = row.name,
    provider.capability = row.capability,
    provider.price_sats = row.price_sats
```

### `create_buyers` (writes)

Adds buyer agents, whether they are admitted, and their starting balance.

```cypher
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
```

### `create_writers` (writes)

Adds outside identities that can write reports but are not buyers.

```cypher
UNWIND $writers AS row
MERGE (:Writer {id: row.id})
```

### `create_wallets` (writes)

Adds intermediate wallets that pass funds along a funding chain.

```cypher
UNWIND $wallet_ids AS wallet_id
MERGE (:Wallet {id: wallet_id})
```

### `create_roots` (writes)

Adds funding roots: the wallets where a funding chain starts.

```cypher
UNWIND $root_ids AS root_id
MERGE (:Wallet:Root {id: root_id})
```

### `link_funding` (writes)

Adds FUNDED_BY links from buyers, writers, providers and wallets to their funder.

```cypher
UNWIND $links AS link
OPTIONAL MATCH (writer:Writer {id: link.funded_id})
OPTIONAL MATCH (provider:Provider {id: link.funded_id})
OPTIONAL MATCH (wallet:Wallet {id: link.funded_id})
WITH link, coalesce(writer, provider, wallet) AS funded
WHERE funded IS NOT NULL
MATCH (funder:Wallet {id: link.funder_id})
MERGE (funded)-[:FUNDED_BY]->(funder)
```

## Finding providers and jobs

### `find_providers` (read-only)

Providers offering a capability, with price, leaving out any a quarantine covers.

```cypher
MATCH (provider:Provider {capability: $capability})
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WITH provider, count(policy) AS policies
WHERE policies = 0
RETURN provider.id AS provider_id, provider.name AS name, provider.price_sats AS price_sats
ORDER BY price_sats, provider_id
```

### `buyer_job` (read-only)

One of this buyer's jobs: what it needs, its input, its status, and the latest decision made for it.

```cypher
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
```

### `provider_listing` (read-only)

A provider's name and listed price in sats.

```cypher
MATCH (provider:Provider {id: $provider_id})
RETURN provider.name AS name, provider.price_sats AS price_sats
```

### `decision_owner` (read-only)

Which buyer made a decision, so one buyer cannot act on another's decision.

```cypher
MATCH (decision:Decision {id: $decision_id})
RETURN decision.buyer_id AS buyer_id
```

## Evidence, the write guard and TRACE scoring

### `candidate_evidence` (read-only)

Everything TRACE needs for one buyer's job, in one round trip: candidate providers with their activity, every visible report marked counted or ignored by the write guard (admission and shared funding within 3 hops), reviewer funders, and the PageRank seeds.

```cypher
MATCH (provider:Provider)
WHERE $capability IS NULL OR provider.capability = $capability
OPTIONAL MATCH ()-[received:REPORTED]->(provider)
WHERE $as_of IS NULL OR received.t <= $as_of
WITH provider, count(received) AS reports_received
OPTIONAL MATCH (payment:Payment)-[:FOR_JOB]->(:Job)-[:FOR]->(provider)
WHERE $as_of IS NULL OR payment.created_at <= $as_of
WITH provider, reports_received, count(payment) AS paid_jobs
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WHERE $as_of IS NULL OR policy.created_at <= $as_of
WITH provider, reports_received, paid_jobs, count(policy) > 0 AS quarantined
OPTIONAL MATCH (provider)-[:FUNDED_BY*1..3]->()<-[:FUNDED_BY*1..3]-(other:Provider)
               <-[:COVERS]-(other_policy:Policy)
WHERE other <> provider AND ($as_of IS NULL OR other_policy.created_at <= $as_of)
WITH provider, reports_received, paid_jobs, quarantined, count(other) > 0 AS contaminated
WITH collect({
  provider_id: provider.id,
  capability: provider.capability,
  price_sats: provider.price_sats,
  reports_received: reports_received,
  paid_jobs: paid_jobs,
  quarantined: quarantined,
  contaminated: contaminated
}) AS providers

OPTIONAL MATCH (writer:Writer)-[report:REPORTED]->(rated:Provider)
WHERE ($capability IS NULL OR rated.capability = $capability)
  AND (writer.id = $me OR report.t <= $others_visible_until)
  AND ($as_of IS NULL OR report.t <= $as_of)

OPTIONAL MATCH (writer)-[:FUNDED_BY*1..3]->(writer_funder)
WITH providers, writer, report, rated, collect(DISTINCT writer_funder.id) AS writer_funders
OPTIONAL MATCH (rated)-[:FUNDED_BY*1..3]->(provider_funder)
WITH providers, writer, report, rated, writer_funders, collect(DISTINCT provider_funder.id) AS provider_funders
WITH providers, writer, report, rated, writer_funders,
     [funder IN writer_funders WHERE funder IN provider_funders] AS shared_funders,
     (writer:Buyer AND coalesce(writer.admitted, false)) AS admitted
WITH providers, writer, report, rated, writer_funders, shared_funders, admitted,
     CASE
       WHEN NOT admitted AND NOT $count_external_writers THEN 'writer_not_admitted'
       WHEN $check_funding AND size(shared_funders) > 0 THEN 'shares_funding_with_provider'
       ELSE null
     END AS ignored_because

WITH providers, collect(CASE WHEN report IS NULL THEN null ELSE {
  provider_id: rated.id,
  writer_id: writer.id,
  admitted: admitted,
  ok: report.ok,
  t: report.t,
  job_id: report.job_id,
  shared_funders: shared_funders,
  ignored_because: ignored_because
} END) AS reports

OPTIONAL MATCH (reviewer:Writer)-[review:REPORTED]->(reviewed:Provider)
WHERE ($capability IS NULL OR reviewed.capability = $capability)
  AND ($as_of IS NULL OR review.t <= $as_of)
WITH DISTINCT providers, reports, reviewer, reviewed
OPTIONAL MATCH (reviewer)-[:FUNDED_BY*1..3]->(funder)
WITH providers, reports, reviewer, reviewed, collect(DISTINCT funder.id) AS funders
WITH providers, reports, collect(CASE WHEN reviewed IS NULL THEN null ELSE {
  provider_id: reviewed.id,
  writer_id: reviewer.id,
  funders: funders
} END) AS reviewer_funders

OPTIONAL MATCH (seed:Buyer)
WHERE seed.admitted = true
WITH providers, reports, reviewer_funders, collect(seed.id) AS admitted_buyers
WITH providers, reports, reviewer_funders, coalesce($seed_writers, admitted_buyers) AS seed_writers

RETURN providers, reports, reviewer_funders, seed_writers
```

### `trace_scores` (read-only)

The same evidence as candidate_evidence, scored inside FalkorDB by the Trace UDF library, so the guard and the TRACE utility run in one query.

```cypher
MATCH (provider:Provider)
WHERE $capability IS NULL OR provider.capability = $capability
OPTIONAL MATCH ()-[received:REPORTED]->(provider)
WHERE $as_of IS NULL OR received.t <= $as_of
WITH provider, count(received) AS reports_received
OPTIONAL MATCH (payment:Payment)-[:FOR_JOB]->(:Job)-[:FOR]->(provider)
WHERE $as_of IS NULL OR payment.created_at <= $as_of
WITH provider, reports_received, count(payment) AS paid_jobs
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
WHERE $as_of IS NULL OR policy.created_at <= $as_of
WITH provider, reports_received, paid_jobs, count(policy) > 0 AS quarantined
OPTIONAL MATCH (provider)-[:FUNDED_BY*1..3]->()<-[:FUNDED_BY*1..3]-(other:Provider)
               <-[:COVERS]-(other_policy:Policy)
WHERE other <> provider AND ($as_of IS NULL OR other_policy.created_at <= $as_of)
WITH provider, reports_received, paid_jobs, quarantined, count(other) > 0 AS contaminated
WITH collect({
  provider_id: provider.id,
  capability: provider.capability,
  price_sats: provider.price_sats,
  reports_received: reports_received,
  paid_jobs: paid_jobs,
  quarantined: quarantined,
  contaminated: contaminated
}) AS providers

OPTIONAL MATCH (writer:Writer)-[report:REPORTED]->(rated:Provider)
WHERE ($capability IS NULL OR rated.capability = $capability)
  AND (writer.id = $me OR report.t <= $others_visible_until)
  AND ($as_of IS NULL OR report.t <= $as_of)

OPTIONAL MATCH (writer)-[:FUNDED_BY*1..3]->(writer_funder)
WITH providers, writer, report, rated, collect(DISTINCT writer_funder.id) AS writer_funders
OPTIONAL MATCH (rated)-[:FUNDED_BY*1..3]->(provider_funder)
WITH providers, writer, report, rated, writer_funders, collect(DISTINCT provider_funder.id) AS provider_funders
WITH providers, writer, report, rated, writer_funders,
     [funder IN writer_funders WHERE funder IN provider_funders] AS shared_funders,
     (writer:Buyer AND coalesce(writer.admitted, false)) AS admitted
WITH providers, writer, report, rated, writer_funders, shared_funders, admitted,
     CASE
       WHEN NOT admitted AND NOT $count_external_writers THEN 'writer_not_admitted'
       WHEN $check_funding AND size(shared_funders) > 0 THEN 'shares_funding_with_provider'
       ELSE null
     END AS ignored_because

WITH providers, collect(CASE WHEN report IS NULL THEN null ELSE {
  provider_id: rated.id,
  writer_id: writer.id,
  admitted: admitted,
  ok: report.ok,
  t: report.t,
  job_id: report.job_id,
  shared_funders: shared_funders,
  ignored_because: ignored_because
} END) AS reports

OPTIONAL MATCH (reviewer:Writer)-[review:REPORTED]->(reviewed:Provider)
WHERE ($capability IS NULL OR reviewed.capability = $capability)
  AND ($as_of IS NULL OR review.t <= $as_of)
WITH DISTINCT providers, reports, reviewer, reviewed
OPTIONAL MATCH (reviewer)-[:FUNDED_BY*1..3]->(funder)
WITH providers, reports, reviewer, reviewed, collect(DISTINCT funder.id) AS funders
WITH providers, reports, collect(CASE WHEN reviewed IS NULL THEN null ELSE {
  provider_id: reviewed.id,
  writer_id: reviewer.id,
  funders: funders
} END) AS reviewer_funders

OPTIONAL MATCH (seed:Buyer)
WHERE seed.admitted = true
WITH providers, reports, reviewer_funders, collect(seed.id) AS admitted_buyers
WITH providers, reports, reviewer_funders, coalesce($seed_writers, admitted_buyers) AS seed_writers

RETURN Trace.scoreCandidates(providers, reports, reviewer_funders, seed_writers, $settings)
       AS scores,
       providers,
       reports
```

## Recording decisions

### `record_decision` (writes)

Stores a trace_score decision for a job, with a RANKED edge to every eligible provider carrying its position and TRACE terms.

```cypher
MATCH (job:Job {id: $job_id})
CREATE (job)-[:DECIDED_BY]->(decision:Decision {
  id: $decision_id,
  buyer_id: $buyer_id,
  status: $status,
  flags: $flags,
  scorer: $scorer,
  view: $view,
  guard: $guard,
  graph_ms: $graph_ms,
  created_at: $t
})
WITH decision
UNWIND $ranked AS row
MATCH (provider:Provider {id: row.provider_id})
CREATE (decision)-[:RANKED {
  position: row.position,
  utility: row.utility,
  lcb: row.lcb,
  risk: row.risk,
  ppr_distance: row.ppr_distance,
  entropy: row.entropy,
  sybil: row.sybil,
  clique: row.clique
}]->(provider)
```

### `record_exclusions` (writes)

Links a decision to the providers it ruled out, with the reason for each.

```cypher
MATCH (decision:Decision {id: $decision_id})
UNWIND $excluded AS row
MATCH (provider:Provider {id: row.provider_id})
CREATE (decision)-[:EXCLUDED {reason: row.reason}]->(provider)
```

### `link_counted_jobs` (writes)

Links a decision to the paid jobs whose outcomes it counted as evidence.

```cypher
MATCH (decision:Decision {id: $decision_id})
UNWIND $job_ids AS job_id
MATCH (job:Job {id: job_id})
CREATE (decision)-[:BASED_ON]->(job)
```

### `record_ignored_claims` (writes)

Keeps every report the guard refused as a Claim node: who wrote it, which provider it is about, and why it was not counted. Links the decision to each one.

```cypher
MATCH (decision:Decision {id: $decision_id})
UNWIND $claims AS row
MATCH (writer:Writer {id: row.writer_id})
MATCH (provider:Provider {id: row.provider_id})
MERGE (claim:Claim {id: row.claim_id})
ON CREATE SET claim.reason = row.reason, claim.ok = row.ok, claim.t = row.t,
              claim.job_id = row.job_id
MERGE (writer)-[:WROTE]->(claim)
MERGE (claim)-[:ABOUT]->(provider)
CREATE (decision)-[:IGNORED]->(claim)
```

## Tasks, hiring, escrow and settlement

### `task_ids` (read-only)

Every task id in the graph, so a restarted server never hands out one already used.

```cypher
MATCH (task:Task)
RETURN task.id AS task_id
```

### `open_task` (writes)

A buyer receives a task and splits it into planned jobs, one per capability.

```cypher
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
```

### `hire_check` (read-only)

Before paying: is the provider in the top 3 of this job's decision, not quarantined, is the job still planned, and can the buyer afford it?

```cypher
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(:Task)-[:SPLIT_INTO]->(job:Job {id: $job_id})
MATCH (provider:Provider {id: $provider_id})
OPTIONAL MATCH (job)-[:DECIDED_BY]->(:Decision {id: $decision_id})-[ranked:RANKED]->(provider)
OPTIONAL MATCH (policy:Policy)-[:COVERS]->(provider)
RETURN job.status AS job_status,
       buyer.balance_sats AS balance_sats,
       provider.price_sats AS price_sats,
       ranked.position AS position,
       collect(policy.id) AS policies
```

### `hold_payment` (writes)

Escrow hold: takes the price from the buyer's balance and records a held Payment for the job, the provider and the decision. Re-checks the hiring rules in the same query.

```cypher
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
```

### `record_delivery` (writes)

Stores what the provider sent back for a job, or that it sent nothing.

```cypher
MATCH (job:Job {id: $job_id})
SET job.output_json = $output_json, job.delivery_note = $note, job.delivered_at = $t
```

### `settle_payment` (writes)

Escrow settle: releases the held payment to the provider on a pass, refunds the buyer on a fail, and writes the buyer's REPORTED outcome edge.

```cypher
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
```

## Outcomes

### `record_settled_jobs` (writes)

Writes finished jobs in one batch: the job, its payment, and the payer's REPORTED edge with the outcome. Used by the simulator, where a round's jobs settle together.

```cypher
UNWIND $jobs AS row
MATCH (payer:Writer {id: row.payer_id})
MATCH (provider:Provider {id: row.provider_id})
CREATE (job:Job {id: row.job_id, capability: provider.capability,
                 price_sats: row.price_sats, created_at: row.t})-[:FOR]->(provider)
CREATE (payment:Payment {id: row.payment_id, sats: row.price_sats,
                         status: CASE WHEN row.ok THEN 'released' ELSE 'defaulted' END,
                         created_at: row.t})-[:FOR_JOB]->(job)
CREATE (payer)-[:MADE]->(payment)
CREATE (payer)-[:REPORTED {ok: row.ok, t: row.t, job_id: row.job_id}]->(provider)
```

### `record_unpaid_reports` (writes)

Writes reports that no paid job backs, the way a cheap Sybil writer would.

```cypher
UNWIND $reports AS row
MATCH (writer:Writer {id: row.writer_id})
MATCH (provider:Provider {id: row.provider_id})
CREATE (writer)-[:REPORTED {ok: row.ok, t: row.t, job_id: null}]->(provider)
```

## Following the money and finding rings

### `funding_path` (read-only)

Shortest chain of FUNDED_BY links, in either direction, between a writer and a provider. A path through a shared wallet or root is the money behind the praise.

```cypher
MATCH (writer:Writer {id: $writer_id}), (provider:Provider {id: $provider_id})
CALL algo.SPpaths({
  sourceNode: writer,
  targetNode: provider,
  relTypes: ['FUNDED_BY'],
  relDirection: 'both',
  maxLen: $max_hops,
  pathCount: 1
})
YIELD path
RETURN [node IN nodes(path) | node.id] AS node_ids,
       [node IN nodes(path) | labels(node)] AS node_labels
```

### `funding_component` (read-only)

Weakly connected components (WCC) over FUNDED_BY: everyone who shares a funding tree with the provider. Money ties are the hard edge of a ring.

```cypher
CALL algo.WCC({nodeLabels: ['Writer', 'Provider', 'Wallet'], relationshipTypes: ['FUNDED_BY']})
YIELD node, componentId
WITH collect({id: node.id, labels: labels(node), component: componentId}) AS assignments
WITH assignments, [entry IN assignments WHERE entry.id = $provider_id][0].component AS target
RETURN [entry IN assignments WHERE entry.component = target | entry] AS members
```

### `praise_community` (read-only)

Community detection by label propagation (CDLP) over funding and reports together: the group the provider is praised and funded within.

```cypher
CALL algo.labelPropagation({
  nodeLabels: ['Writer', 'Provider', 'Wallet'],
  relationshipTypes: ['FUNDED_BY', 'REPORTED'],
  maxIterations: 20
})
YIELD node, communityId
WITH collect({id: node.id, community: communityId}) AS assignments
WITH assignments, [entry IN assignments WHERE entry.id = $provider_id][0].community AS target
RETURN [entry IN assignments WHERE entry.community = target | entry.id] AS community
```

### `funding_pagerank` (read-only)

PageRank over FUNDED_BY: money flows up to funders, so the hub funder ranks first.

```cypher
CALL algo.pageRank(null, 'FUNDED_BY')
YIELD node, score
WITH node, score
WHERE node.id IN $member_ids
RETURN node.id AS id, score
ORDER BY score DESC, id
```

### `funding_betweenness` (read-only)

Betweenness over FUNDED_BY: the wallet most funding paths pass through.

```cypher
CALL algo.betweenness({
  nodeLabels: ['Writer', 'Provider', 'Wallet'],
  relationshipTypes: ['FUNDED_BY']
})
YIELD node, score
WITH node, score
WHERE node.id IN $member_ids
RETURN node.id AS id, score
ORDER BY score DESC, id
```

### `praise_inside` (read-only)

Reports written by members of a funding component about providers in it.

```cypher
MATCH (writer:Writer)-[report:REPORTED]->(provider:Provider)
WHERE writer.id IN $member_ids AND provider.id IN $member_ids
RETURN writer.id AS writer_id,
       coalesce(writer.admitted, false) AS admitted,
       provider.id AS provider_id,
       count(report) AS reports
```

## Quarantine

### `record_funding_trace` (writes)

Notes on the decision that the agent traced the money from a writer to a provider.

```cypher
MATCH (decision:Decision {id: $decision_id})
MATCH (provider:Provider {id: $provider_id})
CREATE (decision)-[:TRACED_FUNDING {
  writer_id: $writer_id,
  node_ids: $node_ids,
  hops: $hops,
  t: $t
}]->(provider)
```

### `record_ring` (writes)

Stores a ring found by find_ring, with MEMBER edges to its providers, writers and wallets, and links the decision that investigated it.

```cypher
MATCH (decision:Decision {id: $decision_id})
MERGE (ring:Ring {id: $ring_id})
ON CREATE SET ring.hub_id = $hub_id,
              ring.bridge_id = $bridge_id,
              ring.size = size($member_ids),
              ring.found_at = $t
CREATE (decision)-[:INVESTIGATED {t: $t}]->(ring)
WITH ring
UNWIND $member_ids AS member_id
OPTIONAL MATCH (writer:Writer {id: member_id})
OPTIONAL MATCH (provider:Provider {id: member_id})
OPTIONAL MATCH (wallet:Wallet {id: member_id})
WITH ring, coalesce(writer, provider, wallet) AS member
WHERE member IS NOT NULL
MERGE (ring)-[:MEMBER]->(member)
```

### `quarantine_ring` (writes)

Writes a quarantine Policy covering every provider in a ring. Only works when the same decision both investigated the ring and found a funding path into it.

```cypher
MATCH (decision:Decision {id: $decision_id})-[:INVESTIGATED]->(ring:Ring {id: $ring_id})
MATCH (decision)-[trace:TRACED_FUNDING]->(traced:Provider)<-[:MEMBER]-(ring)
WHERE trace.hops > 0
WITH decision, ring, count(traced) AS traced_into_ring
WHERE traced_into_ring > 0
CREATE (policy:Policy {
  id: $policy_id,
  kind: 'quarantine',
  reason: $reason,
  created_by: decision.buyer_id,
  created_at: $t
})
CREATE (policy)-[:JUSTIFIED_BY]->(decision)
CREATE (policy)-[:TARGETS]->(ring)
WITH policy, ring
MATCH (ring)-[:MEMBER]->(provider:Provider)
CREATE (policy)-[:COVERS]->(provider)
RETURN policy.id AS policy_id, policy.created_by AS created_by, collect(provider.id) AS covered
```

### `active_policies` (read-only)

Every quarantine in force, with who wrote it, why, and which providers it covers.

```cypher
MATCH (policy:Policy {kind: 'quarantine'})-[:COVERS]->(provider:Provider)
OPTIONAL MATCH (policy)-[:JUSTIFIED_BY]->(decision:Decision)
RETURN policy.id AS policy_id,
       policy.reason AS reason,
       policy.created_by AS created_by,
       policy.created_at AS created_at,
       decision.id AS decision_id,
       collect(provider.id) AS covered
ORDER BY created_at
```

## Lessons and memory recall

### `classify_evidence` (read-only)

Says what kind of node each id is, so a lesson can only cite things that exist.

```cypher
UNWIND $ids AS id
OPTIONAL MATCH (decision:Decision {id: id})
OPTIONAL MATCH (policy:Policy {id: id})
OPTIONAL MATCH (provider:Provider {id: id})
OPTIONAL MATCH (ring:Ring {id: id})
OPTIONAL MATCH (payment:Payment {id: id})
OPTIONAL MATCH (job:Job {id: id})
RETURN id,
       CASE
         WHEN decision IS NOT NULL THEN 'Decision'
         WHEN policy IS NOT NULL THEN 'Policy'
         WHEN provider IS NOT NULL THEN 'Provider'
         WHEN ring IS NOT NULL THEN 'Ring'
         WHEN payment IS NOT NULL THEN 'Payment'
         WHEN job IS NOT NULL THEN 'Job'
         ELSE null
       END AS kind
```

### `write_lesson` (writes)

Stores a lesson a buyer learned, embedded for vector search, linked FROM the decisions and policies that taught it and ABOUT the providers and rings it concerns.

```cypher
MATCH (buyer:Buyer {id: $buyer_id})
CREATE (buyer)-[:LEARNED]->(lesson:Lesson {
  id: $lesson_id,
  text: $text,
  created_at: $t,
  embedding: vecf32($embedding)
})
WITH lesson
OPTIONAL MATCH (decision:Decision) WHERE decision.id IN $source_ids
OPTIONAL MATCH (policy:Policy) WHERE policy.id IN $source_ids
OPTIONAL MATCH (provider:Provider) WHERE provider.id IN $subject_ids
OPTIONAL MATCH (ring:Ring) WHERE ring.id IN $subject_ids
WITH lesson,
     collect(DISTINCT decision) + collect(DISTINCT policy) AS sources,
     collect(DISTINCT provider) + collect(DISTINCT ring) AS subjects
FOREACH (source IN sources | CREATE (lesson)-[:FROM]->(source))
FOREACH (subject IN subjects | CREATE (lesson)-[:ABOUT]->(subject))
RETURN lesson.id AS lesson_id, size(sources) AS sources, size(subjects) AS subjects
```

### `similar_lessons` (read-only)

Lessons closest to the task text, from the Lesson vector index, with what they cite.

```cypher
CALL db.idx.vector.queryNodes('Lesson', 'embedding', $k, vecf32($query_vector))
YIELD node, score
OPTIONAL MATCH (author:Buyer)-[:LEARNED]->(node)
OPTIONAL MATCH (node)-[:FROM]->(source)
OPTIONAL MATCH (node)-[:ABOUT]->(subject)
OPTIONAL MATCH (node)-[:ABOUT]->(:Ring)-[:MEMBER]->(ring_provider:Provider)
RETURN node.id AS lesson_id,
       node.text AS text,
       node.created_at AS created_at,
       author.id AS author_id,
       score,
       collect(DISTINCT source.id) AS source_ids,
       collect(DISTINCT subject.id) AS subject_ids,
       collect(DISTINCT ring_provider.id) AS ring_provider_ids
ORDER BY score
```

### `recent_lessons` (read-only)

The newest lessons, used when no embedding is available.

```cypher
MATCH (author:Buyer)-[:LEARNED]->(node:Lesson)
OPTIONAL MATCH (node)-[:FROM]->(source)
OPTIONAL MATCH (node)-[:ABOUT]->(subject)
OPTIONAL MATCH (node)-[:ABOUT]->(:Ring)-[:MEMBER]->(ring_provider:Provider)
RETURN node.id AS lesson_id,
       node.text AS text,
       node.created_at AS created_at,
       author.id AS author_id,
       null AS score,
       collect(DISTINCT source.id) AS source_ids,
       collect(DISTINCT subject.id) AS subject_ids,
       collect(DISTINCT ring_provider.id) AS ring_provider_ids
ORDER BY created_at DESC
LIMIT $k
```

### `past_decisions` (read-only)

A buyer's own recent decisions: what it needed, whom it chose, and how it ended.

```cypher
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(:Task)-[:SPLIT_INTO]->(job:Job)
      -[:DECIDED_BY]->(decision:Decision)
OPTIONAL MATCH (decision)-[:CHOSE]->(provider:Provider)
OPTIONAL MATCH (payment:Payment)-[:FOR_DECISION]->(decision)
RETURN decision.id AS decision_id,
       decision.created_at AS created_at,
       decision.status AS status,
       decision.flags AS flags,
       job.capability AS capability,
       provider.id AS provider_id,
       provider.name AS provider_name,
       payment.status AS payment_status,
       payment.sats AS sats,
       payment.verdict_reason AS verdict_reason
ORDER BY created_at DESC
LIMIT $limit
```

### `pooled_trust` (read-only)

For each provider this buyer has used: the outcomes every admitted buyer reported, pooled, and how many buyers they came from.

```cypher
MATCH (buyer:Buyer {id: $buyer_id})-[:REPORTED]->(provider:Provider)
WITH DISTINCT provider
MATCH (peer:Buyer)-[report:REPORTED]->(provider)
WHERE peer.admitted = true
RETURN provider.id AS provider_id,
       provider.name AS provider_name,
       provider.capability AS capability,
       count(CASE WHEN report.ok = true THEN 1 END) AS successes,
       count(CASE WHEN report.ok = false THEN 1 END) AS failures,
       count(DISTINCT peer) AS buyers
ORDER BY provider_id
```

## Receipts and accountability

### `decision_receipt` (read-only)

The receipt for a decision: how it ranked providers, whom it ruled out and why, how many paid jobs it counted, the claims it ignored, what was investigated, and the payment.

```cypher
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
```

### `who_authorised` (read-only)

Who stands behind a payment: the principal that owns the buyer, the task, the job, the decision and the provider paid.

```cypher
MATCH (principal:Principal)-[:OWNS]->(buyer:Buyer)-[:MADE]->(payment:Payment {id: $payment_id})
MATCH (payment)-[:FOR_JOB]->(job:Job)<-[:SPLIT_INTO]-(task:Task)<-[:RECEIVED]-(buyer)
OPTIONAL MATCH (payment)-[:FOR_DECISION]->(decision:Decision)
OPTIONAL MATCH (job)-[:FOR]->(provider:Provider)
RETURN principal.id AS principal_id, principal.name AS principal_name, buyer.id AS buyer_id,
       task.id AS task_id, task.text AS task_text, job.id AS job_id,
       job.capability AS capability, decision.id AS decision_id, decision.status AS status,
       provider.id AS provider_id, payment.sats AS sats, payment.status AS payment_status
```

### `known_ids` (read-only)

Which of a list of ids exist as nodes, used to check every id the agent cites.

```cypher
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
```

## What if: replaying a decision with another guard

### `recorded_decision` (read-only)

What a stored decision was made with: the job's capability, the buyer, view, guard, scorer and time, its ranking in order, and the provider it chose.

```cypher
MATCH (job:Job)-[:DECIDED_BY]->(decision:Decision {id: $decision_id})
OPTIONAL MATCH (decision)-[ranked:RANKED]->(provider:Provider)
WITH job, decision, ranked, provider ORDER BY ranked.position
WITH job, decision, collect(provider.id) AS ranked_ids
OPTIONAL MATCH (decision)-[:CHOSE]->(chosen:Provider)
RETURN decision.id AS decision_id, job.id AS job_id, decision.buyer_id AS buyer_id,
       job.capability AS capability, decision.view AS view, decision.guard AS guard,
       decision.scorer AS scorer, decision.created_at AS t, ranked_ids,
       chosen.id AS chosen_id
```

### `provider_since` (read-only)

What happened to some providers after a moment: quarantines that now cover them, and how their paid jobs ended.

```cypher
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
```

## Read-only views for the API and the investigator

### `job_story` (read-only)

One job from task to outcome: who asked for it, the decisions made for it, the provider hired, the payment and how it ended, and the judge's reason.

```cypher
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
```

### `recent_jobs` (read-only)

The newest jobs in the market with their provider and how the payment ended, optionally only released or refunded ones: how the investigator finds 'job 14'.

```cypher
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
```

### `funding_chain` (read-only)

Who funds a node, up to 3 FUNDED_BY hops, and who else draws on the same funders: the money behind a writer or a provider.

```cypher
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
```

### `neighbourhood` (read-only)

Every node within one or two hops of a node, with the edges between them.

```cypher
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
```

### `graph_snapshot` (read-only)

The market as the graph view draws it: every node except stored embeddings, and every edge between them, capped for the browser.

```cypher
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
```

## Scoreboard

### `round_reports` (read-only)

The scoreboard's one read per round: every report written in the last round, each marked counted or ignored by the same write guard the agents' evidence query uses.

```cypher
MATCH (writer:Writer)-[report:REPORTED]->(rated:Provider)
WHERE report.t = $t

OPTIONAL MATCH (writer)-[:FUNDED_BY*1..3]->(writer_funder)
WITH writer, report, rated, collect(DISTINCT writer_funder.id) AS writer_funders
OPTIONAL MATCH (rated)-[:FUNDED_BY*1..3]->(provider_funder)
WITH writer, report, rated, writer_funders, collect(DISTINCT provider_funder.id) AS provider_funders
WITH writer, report, rated, writer_funders,
     [funder IN writer_funders WHERE funder IN provider_funders] AS shared_funders,
     (writer:Buyer AND coalesce(writer.admitted, false)) AS admitted
WITH writer, report, rated, writer_funders, shared_funders, admitted,
     CASE
       WHEN NOT admitted AND NOT $count_external_writers THEN 'writer_not_admitted'
       WHEN $check_funding AND size(shared_funders) > 0 THEN 'shares_funding_with_provider'
       ELSE null
     END AS ignored_because

RETURN rated.id AS provider_id,
       writer.id AS writer_id,
       admitted,
       report.ok AS ok,
       report.t AS t,
       report.job_id AS job_id,
       shared_funders,
       ignored_because,
       writer_funders
ORDER BY writer_id, report.job_id
```

### `record_sim_decision` (writes)

A bare Decision for the scoreboard's scripted investigator, so funding_path, find_ring and quarantine are written onto a decision exactly as the agent's are.

```cypher
CREATE (:Decision {id: $decision_id, buyer_id: $buyer_id, status: 'flagged', t: $t})
```

### `quarantine_state` (read-only)

Providers under a quarantine Policy, and providers that share funding within 3 hops with one of them: the two hard filters a quarantine adds to scoring.

```cypher
MATCH (:Policy)-[:COVERS]->(covered:Provider)
WITH collect(DISTINCT covered) AS covered
UNWIND covered AS member
OPTIONAL MATCH (member)-[:FUNDED_BY*1..3]->()<-[:FUNDED_BY*1..3]-(near:Provider)
WHERE NOT near IN covered
RETURN [provider IN covered | provider.id] AS quarantined,
       collect(DISTINCT near.id) AS contaminated
```

### `save_scoreboard` (writes)

Stores one scoreboard run: the frozen settings hash, a summary per lane and adversary, and every seed's result, so the API reads numbers from FalkorDB. A run already stored under the same id is left alone, so a kept copy can be stored again after a restart.

```cypher
OPTIONAL MATCH (old:ScoreboardRun {id: $run_id})
WITH count(old) AS already_stored WHERE already_stored = 0
CREATE (run:ScoreboardRun {
  id: $run_id, settings_hash: $settings_hash, settings: $settings,
  seeds: $seeds, demo_seed: $demo_seed, created_at: $t
})
WITH run
UNWIND $lanes AS lane
CREATE (run)-[:MEASURED]->(summary:LaneResult {
  lane: lane.lane, adversary: lane.adversary, seeds: lane.seeds,
  mean: lane.mean, se: lane.se, median: lane.median, p90: lane.p90, max: lane.max,
  malicious_share: lane.malicious_share, mean_round_ms: lane.mean_round_ms
})
WITH summary, lane
UNWIND lane.results AS result
CREATE (summary)-[:FROM_SEED]->(:SeedResult {
  seed: result.seed, fraud_sats: result.fraud_sats, jobs: result.jobs,
  malicious_jobs: result.malicious_jobs, attacker_spend_sats: result.attacker_spend_sats,
  quarantined_at_round: result.quarantined_at_round
})
```

### `latest_scoreboard` (read-only)

The newest scoreboard run with its lane summaries.

```cypher
MATCH (run:ScoreboardRun)
WITH run ORDER BY run.created_at DESC LIMIT 1
MATCH (run)-[:MEASURED]->(lane:LaneResult)
RETURN run.id AS run_id, run.settings_hash AS settings_hash, run.seeds AS seeds,
       run.demo_seed AS demo_seed, run.created_at AS created_at,
       collect(lane {.*}) AS lanes
```

## Agent evals

### `save_agent_eval` (writes)

Stores one agent eval run: L1 per lane (same model with and without the graph), the L2 tool-choice score, and every case with the tool path the agent took. A run already stored under the same id is left alone.

```cypher
OPTIONAL MATCH (old:AgentEvalRun {id: $run_id})
WITH count(old) AS already_stored WHERE already_stored = 0
CREATE (run:AgentEvalRun {
  id: $run_id, model: $model, cases: $cases, created_at: $t,
  ring_cases: $l2.ring_cases, rings_investigated: $l2.rings_investigated,
  other_cases_investigated: $l2.other_cases_investigated,
  precision: $l2.precision, recall: $l2.recall,
  quarantines: $l2.quarantines, quarantines_backed: $l2.quarantines_backed,
  false_quarantines: $l2.false_quarantines, citation_pass_rate: $l2.citation_pass_rate
})
WITH run
UNWIND $lanes AS lane
CREATE (run)-[:MEASURED]->(:AgentEvalLane {
  lane: lane.lane, cases: lane.cases, scams_hired: lane.scams_hired,
  sats_to_scams: lane.sats_to_scams, rings_hired: lane.rings_hired,
  no_hire: lane.no_hire, errors: lane.errors
})
WITH DISTINCT run
UNWIND $case_runs AS case_run
CREATE (run)-[:RAN]->(:EvalCase {
  case_id: case_run.case_id, kind: case_run.kind, label: case_run.label,
  lane: case_run.lane, hired: case_run.hired, hired_malicious: case_run.hired_malicious,
  tool_path: case_run.tool_path, investigated: case_run.investigated,
  quarantined: case_run.quarantined, error: case_run.error
})
```

### `latest_agent_eval` (read-only)

The newest agent eval run with its per-lane results.

```cypher
MATCH (run:AgentEvalRun)
WITH run ORDER BY run.created_at DESC LIMIT 1
MATCH (run)-[:MEASURED]->(lane:AgentEvalLane)
RETURN run {.*} AS run, collect(lane {.*}) AS lanes
```

## Operations

### `add_spend` (writes)

Adds one paid LLM call's tokens and cost to the spend meter in the ops graph.

```cypher
MERGE (meter:SpendMeter {id: 'llm'})
ON CREATE SET meter.usd = 0.0, meter.calls = 0, meter.input_tokens = 0,
              meter.cached_tokens = 0, meter.output_tokens = 0
SET meter.usd = meter.usd + $usd,
    meter.calls = meter.calls + 1,
    meter.input_tokens = meter.input_tokens + $input_tokens,
    meter.cached_tokens = meter.cached_tokens + $cached_tokens,
    meter.output_tokens = meter.output_tokens + $output_tokens,
    meter.updated_at = $t
RETURN meter.usd AS usd
```

### `read_spend` (read-only)

Reads the spend meter: dollars spent on the paid LLM and tokens used.

```cypher
OPTIONAL MATCH (meter:SpendMeter {id: 'llm'})
RETURN coalesce(meter.usd, 0.0) AS usd,
       coalesce(meter.calls, 0) AS calls,
       coalesce(meter.input_tokens, 0) AS input_tokens,
       coalesce(meter.cached_tokens, 0) AS cached_tokens,
       coalesce(meter.output_tokens, 0) AS output_tokens
```

### `count_question` (writes)

Counts one investigator question for a visitor and returns their running total.

```cypher
MERGE (visitor:Visitor {id: $visitor_id})
SET visitor.questions = coalesce(visitor.questions, 0) + 1,
    visitor.last_seen = $t
RETURN visitor.questions AS questions
```
