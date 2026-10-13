from tracegraph.graph.queries.query import Query

SAVE_AGENT_EVAL = Query(
    name="save_agent_eval",
    purpose=(
        "Stores one agent eval run: L1 per lane (same model with and without the graph), the "
        "L2 tool-choice score, and every case with the tool path the agent took. A run already "
        "stored under the same id is left alone."
    ),
    read_only=False,
    text="""
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
""",
)

LATEST_AGENT_EVAL = Query(
    name="latest_agent_eval",
    purpose="The newest agent eval run with its per-lane results.",
    text="""
MATCH (run:AgentEvalRun)
WITH run ORDER BY run.created_at DESC LIMIT 1
MATCH (run)-[:MEASURED]->(lane:AgentEvalLane)
RETURN run {.*} AS run, collect(lane {.*}) AS lanes
""",
)
