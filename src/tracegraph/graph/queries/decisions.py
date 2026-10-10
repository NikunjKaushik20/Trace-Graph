from tracegraph.graph.queries.query import Query

RECORD_DECISION = Query(
    name="record_decision",
    purpose=(
        "Stores a trace_score decision for a job, with a RANKED edge to every eligible "
        "provider carrying its position and TRACE terms."
    ),
    read_only=False,
    text="""
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
""",
)

RECORD_EXCLUSIONS = Query(
    name="record_exclusions",
    purpose="Links a decision to the providers it ruled out, with the reason for each.",
    read_only=False,
    text="""
MATCH (decision:Decision {id: $decision_id})
UNWIND $excluded AS row
MATCH (provider:Provider {id: row.provider_id})
CREATE (decision)-[:EXCLUDED {reason: row.reason}]->(provider)
""",
)

LINK_COUNTED_JOBS = Query(
    name="link_counted_jobs",
    purpose="Links a decision to the paid jobs whose outcomes it counted as evidence.",
    read_only=False,
    text="""
MATCH (decision:Decision {id: $decision_id})
UNWIND $job_ids AS job_id
MATCH (job:Job {id: job_id})
CREATE (decision)-[:BASED_ON]->(job)
""",
)

RECORD_IGNORED_CLAIMS = Query(
    name="record_ignored_claims",
    purpose=(
        "Keeps every report the guard refused as a Claim node: who wrote it, which provider it "
        "is about, and why it was not counted. Links the decision to each one."
    ),
    read_only=False,
    text="""
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
""",
)
