from tracegraph.graph.queries.query import Query

CANDIDATE_PROVIDERS = """
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
"""


# The write guard as a Cypher fragment: whether each report counts, from admission and funding
def report_guard(carried: str) -> str:
    keep = f"{carried}writer, report, rated"
    return f"""
OPTIONAL MATCH (writer)-[:FUNDED_BY*1..3]->(writer_funder)
WITH {keep}, collect(DISTINCT writer_funder.id) AS writer_funders
OPTIONAL MATCH (rated)-[:FUNDED_BY*1..3]->(provider_funder)
WITH {keep}, writer_funders, collect(DISTINCT provider_funder.id) AS provider_funders
WITH {keep}, writer_funders,
     [funder IN writer_funders WHERE funder IN provider_funders] AS shared_funders,
     (writer:Buyer AND coalesce(writer.admitted, false)) AS admitted
WITH {keep}, writer_funders, shared_funders, admitted,
     CASE
       WHEN NOT admitted AND NOT $count_external_writers THEN 'writer_not_admitted'
       WHEN $check_funding AND size(shared_funders) > 0 THEN 'shares_funding_with_provider'
       ELSE null
     END AS ignored_because
"""


GUARDED_REPORTS = (
    """
OPTIONAL MATCH (writer:Writer)-[report:REPORTED]->(rated:Provider)
WHERE ($capability IS NULL OR rated.capability = $capability)
  AND (writer.id = $me OR report.t <= $others_visible_until)
  AND ($as_of IS NULL OR report.t <= $as_of)
"""
    + report_guard("providers, ")
    + """
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
"""
)

REVIEWER_FUNDERS = """
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
"""

SEED_WRITERS = """
OPTIONAL MATCH (seed:Buyer)
WHERE seed.admitted = true
WITH providers, reports, reviewer_funders, collect(seed.id) AS admitted_buyers
WITH providers, reports, reviewer_funders, coalesce($seed_writers, admitted_buyers) AS seed_writers
"""

EVIDENCE_PARTS = CANDIDATE_PROVIDERS + GUARDED_REPORTS + REVIEWER_FUNDERS + SEED_WRITERS

CANDIDATE_EVIDENCE = Query(
    name="candidate_evidence",
    purpose=(
        "Everything TRACE needs for one buyer's job, in one round trip: candidate providers "
        "with their activity, every visible report marked counted or ignored by the write guard "
        "(admission and shared funding within 3 hops), reviewer funders, and the PageRank seeds."
    ),
    text=EVIDENCE_PARTS
    + """
RETURN providers, reports, reviewer_funders, seed_writers
""",
)

TRACE_SCORES = Query(
    name="trace_scores",
    purpose=(
        "The same evidence as candidate_evidence, scored inside FalkorDB by the Trace UDF "
        "library, so the guard and the TRACE utility run in one query."
    ),
    text=EVIDENCE_PARTS
    + """
RETURN Trace.scoreCandidates(providers, reports, reviewer_funders, seed_writers, $settings)
       AS scores,
       providers,
       reports
""",
)
