import type { AgentEvent, PlannedJob } from "../api/types";

export interface ToolStep {
  index: number;
  jobId: string;
  name: string;
  arguments: Record<string, unknown>;
  ok?: boolean;
  result?: Record<string, unknown> | string;
  startedAt: number;
  finishedAt?: number;
}

export interface Escrow {
  providerId: string;
  providerName?: string;
  paymentId: string;
  sats: number;
  status: "held" | "released" | "refunded";
  judgeReason?: string;
}

export interface JobRun {
  job: PlannedJob;
  steps: ToolStep[];
  decisionIds: string[];
  escrow?: Escrow;
  narration?: string;
  citations?: { cited: string[]; unknown: string[] };
  error?: string;
}

export interface RunState {
  taskId: string | null;
  buyerId: string;
  status: "idle" | "starting" | "running" | "done" | "failed";
  jobs: JobRun[];
  error?: string;
}

export const IDLE_RUN: RunState = { taskId: null, buyerId: "buyer-1", status: "idle", jobs: [] };

// The result of a step as an object, or an empty one for refusals
export function resultOf(step: ToolStep): Record<string, unknown> {
  return typeof step.result === "object" && step.result !== null ? step.result : {};
}

// Applies a tool result's money and decision facts to its job
function applyResult(run: JobRun, step: ToolStep): JobRun {
  const result = resultOf(step);
  if (step.name === "trace_score" && typeof result.decision_id === "string") {
    return { ...run, decisionIds: [...run.decisionIds, result.decision_id] };
  }
  if (step.name === "hire_with_escrow" && step.ok) {
    const escrow: Escrow = {
      providerId: String(result.provider_id),
      providerName: typeof result.provider_name === "string" ? result.provider_name : undefined,
      paymentId: String(result.payment_id),
      sats: Number(result.held_sats),
      status: "held",
    };
    return { ...run, escrow };
  }
  if (step.name === "settle" && step.ok && run.escrow) {
    const status = result.status === "refunded" ? "refunded" : "released";
    return { ...run, escrow: { ...run.escrow, status, judgeReason: String(result.judge_reason ?? "") } };
  }
  return run;
}

// Changes one job in the run, adding it if the plan did not mention it
function withJob(state: RunState, jobId: string, change: (run: JobRun) => JobRun): RunState {
  const known = state.jobs.some((run) => run.job.job_id === jobId);
  const jobs = known
    ? state.jobs
    : [...state.jobs, { job: { job_id: jobId, capability: "", input_text: "" }, steps: [], decisionIds: [] }];
  return { ...state, jobs: jobs.map((run) => (run.job.job_id === jobId ? change(run) : run)) };
}

// Folds one event from the agent's stream into the run
export function applyEvent(state: RunState, event: AgentEvent): RunState {
  const jobId = event.job_id ?? "";
  if (event.kind === "plan") {
    const planned = (event.data.jobs as PlannedJob[]) ?? [];
    return { ...state, status: "running", jobs: planned.map((job) => ({ job, steps: [], decisionIds: [] })) };
  }
  if (event.kind === "tool_call") {
    return withJob(state, jobId, (run) => {
      const step: ToolStep = {
        index: run.steps.length,
        jobId,
        name: String(event.data.name),
        arguments: (event.data.arguments as Record<string, unknown>) ?? {},
        startedAt: event.t,
      };
      return { ...run, steps: [...run.steps, step] };
    });
  }
  if (event.kind === "tool_result") {
    return withJob(state, jobId, (run) => {
      const last = run.steps[run.steps.length - 1];
      if (!last) return run;
      const done: ToolStep = {
        ...last,
        ok: Boolean(event.data.ok),
        result: event.data.result as ToolStep["result"],
        finishedAt: event.t,
      };
      return applyResult({ ...run, steps: [...run.steps.slice(0, -1), done] }, done);
    });
  }
  if (event.kind === "narration") {
    return withJob(state, jobId, (run) => ({
      ...run,
      narration: String(event.data.text ?? ""),
      citations: { cited: (event.data.cited as string[]) ?? [], unknown: (event.data.unknown as string[]) ?? [] },
    }));
  }
  return withJob(state, jobId, (run) => ({ ...run, error: String(event.data.message ?? "error") }));
}
