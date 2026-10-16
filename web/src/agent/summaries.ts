import { resultOf, type ToolStep } from "./steps";

export const TOOL_TITLES: Record<string, string> = {
  recall_memory: "Recall memory",
  find_providers: "Find providers",
  trace_score: "Score with TRACE",
  funding_path: "Follow the money",
  find_ring: "Find the ring",
  quarantine: "Quarantine the ring",
  hire_with_escrow: "Hire with escrow",
  settle: "Judge and settle",
  explain_decision: "Explain a decision",
  write_lesson: "Write a lesson",
  who_authorised: "Who authorised",
};

// A list's length, or zero when the field is missing
function count(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

// The algorithms a result says it ran, in readable form
export function algorithmsOf(step: ToolStep): string[] {
  const result = resultOf(step);
  const names = [...(Array.isArray(result.algorithms) ? result.algorithms : [])];
  if (typeof result.algorithm === "string") names.push(result.algorithm);
  return names.map((name) => String(name));
}

// One line saying what a finished step found, in the words a person would use
export function summarise(step: ToolStep): string {
  if (step.ok === undefined) return "Running…";
  if (!step.ok) return typeof step.result === "string" ? step.result.replace(/^Error executing tool \w+: /, "") : "Refused";
  const result = resultOf(step);
  switch (step.name) {
    case "recall_memory":
      return `${count(result.past_decisions)} past decisions, ${count(result.pooled_trust)} providers the fleet has used, ${count(result.quarantines)} quarantines, ${count(result.lessons)} lessons`;
    case "find_providers":
      return `${count(result.providers)} providers offer ${String(result.capability).replace("_", " ")}`;
    case "trace_score": {
      const status = result.status === "flagged" ? "Flagged" : "Confident";
      return `${status}: ${count(result.hireable)} hireable, ${count(result.excluded)} ruled out`;
    }
    case "funding_path":
      return result.found
        ? `${result.hops} hops: ${(result.path as string[]).join(" → ")}`
        : "No funding path between them";
    case "find_ring":
      return result.is_ring
        ? `A ring: ${count(result.providers)} providers, ${result.writer_count} writers, hub ${result.hub_funder}`
        : "Not a ring";
    case "quarantine":
      return `Blocked ${(result.covered as string[]).join(", ")}`;
    case "hire_with_escrow":
      return `${result.held_sats} sats held for ${result.provider_name ?? result.provider_id}`;
    case "settle":
      return `${result.status === "refunded" ? "Refunded" : "Released"} ${result.sats} sats: ${result.judge_reason}`;
    case "write_lesson":
      return `Saved ${result.lesson_id ?? "a lesson"}`;
    default:
      return "Done";
  }
}

// Milliseconds FalkorDB spent on a step, when the tool reported it
export function graphMs(step: ToolStep): number | null {
  const value = resultOf(step).graph_ms;
  return typeof value === "number" ? value : null;
}
