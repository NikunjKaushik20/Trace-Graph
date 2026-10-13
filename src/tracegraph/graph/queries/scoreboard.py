from tracegraph.graph.queries.evidence import report_guard
from tracegraph.graph.queries.query import Query

ROUND_REPORTS = Query(
    name="round_reports",
    purpose=(
        "The scoreboard's one read per round: every report written in the last round, each "
        "marked counted or ignored by the same write guard the agents' evidence query uses."
    ),
    text="""
MATCH (writer:Writer)-[report:REPORTED]->(rated:Provider)
WHERE report.t = $t
"""
    + report_guard("")
    + """
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
""",
)

RECORD_SIM_DECISION = Query(
    name="record_sim_decision",
    purpose=(
        "A bare Decision for the scoreboard's scripted investigator, so funding_path, find_ring "
        "and quarantine are written onto a decision exactly as the agent's are."
    ),
    read_only=False,
    text="""
CREATE (:Decision {id: $decision_id, buyer_id: $buyer_id, status: 'flagged', t: $t})
""",
)

QUARANTINE_STATE = Query(
    name="quarantine_state",
    purpose=(
        "Providers under a quarantine Policy, and providers that share funding within 3 hops "
        "with one of them: the two hard filters a quarantine adds to scoring."
    ),
    text="""
MATCH (:Policy)-[:COVERS]->(covered:Provider)
WITH collect(DISTINCT covered) AS covered
UNWIND covered AS member
OPTIONAL MATCH (member)-[:FUNDED_BY*1..3]->()<-[:FUNDED_BY*1..3]-(near:Provider)
WHERE NOT near IN covered
RETURN [provider IN covered | provider.id] AS quarantined,
       collect(DISTINCT near.id) AS contaminated
""",
)

SAVE_SCOREBOARD = Query(
    name="save_scoreboard",
    purpose=(
        "Stores one scoreboard run: the frozen settings hash, a summary per lane and adversary, "
        "and every seed's result, so the API reads numbers from FalkorDB. A run already stored "
        "under the same id is left alone, so a kept copy can be stored again after a restart."
    ),
    read_only=False,
    text="""
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
""",
)

LATEST_SCOREBOARD = Query(
    name="latest_scoreboard",
    purpose="The newest scoreboard run with its lane summaries.",
    text="""
MATCH (run:ScoreboardRun)
WITH run ORDER BY run.created_at DESC LIMIT 1
MATCH (run)-[:MEASURED]->(lane:LaneResult)
RETURN run.id AS run_id, run.settings_hash AS settings_hash, run.seeds AS seeds,
       run.demo_seed AS demo_seed, run.created_at AS created_at,
       collect(lane {.*}) AS lanes
""",
)
