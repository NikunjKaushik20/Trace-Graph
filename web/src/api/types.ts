export type GuardMode = "closed" | "open" | "unguarded";
export type View = "together" | "alone";

export interface Health {
  falkordb: "up" | "down";
  unplugged: boolean;
  can_pay: boolean;
  guard_mode: GuardMode;
  llm_mode: "live" | "record" | "replay";
  scorer: "udf" | "python";
}

export interface GraphNode {
  id: string;
  labels: string[];
  name: string | null;
  status: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface Snapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  graph: string;
  graph_ms: number;
}

export interface PlannedJob {
  job_id: string;
  capability: string;
  input_text: string;
}

export interface AgentEvent {
  kind: "plan" | "tool_call" | "tool_result" | "narration" | "error";
  buyer_id: string;
  job_id: string | null;
  data: Record<string, unknown>;
  t: number;
}

export interface TaskStarted {
  task_id: string;
  buyer_id: string;
  events_url: string;
}

export interface RankedProvider {
  provider_id: string;
  position: number;
  utility: number;
  lcb: number;
  risk: number;
  sybil: number;
  clique: number;
}

export interface Receipt {
  decision_id: string;
  buyer_id: string;
  status: string;
  flags: string[];
  scorer: string;
  view: View;
  guard: GuardMode;
  graph_ms: number;
  job_id: string;
  capability: string;
  ranked: RankedProvider[];
  excluded: { provider_id: string; reason: string }[];
  ignored: { provider_id: string; reason: string; claims: number }[];
  counted_jobs: number;
  funding_traces: { hops: number; node_ids: string[]; provider_id: string; writer_id: string }[];
  rings: string[];
  policies: string[];
  chosen_id: string | null;
  payment_id: string | null;
  payment_status: string | null;
  sats: number | null;
  verdict_reason: string | null;
  queries: { name: string; purpose: string }[];
}

export interface WhatIfShift {
  provider_id: string;
  utility_before: number;
  utility_after: number;
  position_before: number;
  position_after: number;
  reports_counted_now: number;
  shared_funders: string[];
}

export interface WhatIf {
  decision_id: string;
  guard_used: GuardMode;
  guard_tried: GuardMode;
  top_used: string | null;
  top_tried: string | null;
  changed: boolean;
  summary: string;
  shifts: WhatIfShift[];
  graph_ms: number;
}

export interface JobSummary {
  buyer_id: string;
  task_id: string;
  job_id: string;
  capability: string;
  provider_id: string | null;
  payment_id: string | null;
  payment_status: string | null;
}

export interface JobStory extends JobSummary {
  task_text: string;
  job_status: string;
  decision_ids: string[];
  sats: number | null;
  judge_reason: string | null;
}

export interface Authorisation {
  principal_id: string;
  principal_name: string;
  buyer_id: string;
  task_id: string;
  job_id: string;
  decision_id: string;
  provider_id: string;
  sats: number;
  payment_status: string;
}

export interface EvalLane {
  lane: "graph" | "text";
  cases: number;
  scams_hired: number;
  sats_to_scams: number;
  no_hire: number;
  errors: number;
}

export interface AgentEval {
  run: {
    cases: number;
    model: string;
    ring_cases: number;
    rings_investigated: number;
    recall: number;
    precision: number;
    quarantines: number;
    quarantines_backed: number;
    false_quarantines: number;
    citation_pass_rate: number;
  };
  lanes: EvalLane[];
}

export type Adversary = "strat" | "calib";

export interface LaneSummary {
  lane: string;
  adversary: Adversary;
  mean: number;
  se: number;
  median: number;
  p90: number;
  seeds: number;
}

export interface Scoreboard {
  run_id: string;
  seeds: number;
  demo_seed: number;
  lanes: LaneSummary[];
}

export interface RoundResult {
  lane: string;
  adversary: string;
  seed: number;
  round: number;
  fraud_sats: number;
  malicious_jobs: number;
  quarantined_at_round: number | null;
  round_ms: number;
}

export interface Answer {
  question: string;
  answer: string;
  tools: { name: string; arguments: Record<string, unknown>; ok: boolean }[];
  path_ids: string[];
  citations_passed: boolean;
  questions_left: number;
}

export interface Spend {
  usd: number;
  limit_usd: number;
  calls: number;
  limit_reached: boolean;
}

export interface QuarantinePolicy {
  policy_id: string;
  reason: string;
  created_by: string;
  decision_id: string | null;
  covered: string[];
}
