from tracegraph.graph.queries.query import Query

RECORD_SETTLED_JOBS = Query(
    name="record_settled_jobs",
    purpose=(
        "Writes finished jobs in one batch: the job, its payment, and the payer's REPORTED edge "
        "with the outcome. Used by the simulator, where a round's jobs settle together."
    ),
    read_only=False,
    text="""
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
""",
)

RECORD_UNPAID_REPORTS = Query(
    name="record_unpaid_reports",
    purpose="Writes reports that no paid job backs, the way a cheap Sybil writer would.",
    read_only=False,
    text="""
UNWIND $reports AS row
MATCH (writer:Writer {id: row.writer_id})
MATCH (provider:Provider {id: row.provider_id})
CREATE (writer)-[:REPORTED {ok: row.ok, t: row.t, job_id: null}]->(provider)
""",
)
