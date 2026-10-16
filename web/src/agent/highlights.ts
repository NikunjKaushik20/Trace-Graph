import type { Snapshot } from "../api/types";
import type { Highlight } from "../graph/draw";
import { resultOf, type RunState, type ToolStep } from "./steps";

// Every string in a list-valued field of a result
function idsIn(result: Record<string, unknown>, ...fields: string[]): string[] {
  return fields.flatMap((field) => {
    const value = result[field];
    if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
    return typeof value === "string" ? [value] : [];
  });
}

// The provider ids in a trace_score ranking
function rankedIds(result: Record<string, unknown>): string[] {
  const hireable = Array.isArray(result.hireable) ? result.hireable : [];
  return hireable.map((entry) => String((entry as { provider_id: string }).provider_id));
}

// What one finished step points at: the nodes the agent is looking at right now
export function focusOf(step: ToolStep): string[] {
  const result = resultOf(step);
  switch (step.name) {
    case "recall_memory":
      return (Array.isArray(result.pooled_trust) ? result.pooled_trust : []).map((row) =>
        String((row as { provider_id: string }).provider_id),
      );
    case "trace_score":
      return rankedIds(result);
    case "funding_path":
      return idsIn(result, "path");
    case "find_ring":
      return result.is_ring ? [] : idsIn(result, "providers", "wallets");
    case "hire_with_escrow":
    case "settle":
      return idsIn(result, "provider_id", "payment_id", "job_id");
    default:
      return idsIn(step.arguments, "provider_id", "job_id", "decision_id");
  }
}

// What one step proved suspicious: rings, the providers they cover, flagged candidates
export function alertsOf(step: ToolStep): string[] {
  const result = resultOf(step);
  if (step.name === "find_ring" && result.is_ring) {
    return idsIn(result, "providers", "writers", "wallets", "ring_id");
  }
  if (step.name === "quarantine") return idsIn(result, "covered", "policy_id");
  if (step.name === "settle" && result.status === "refunded") return idsIn(result, "payment_id");
  if (step.name === "trace_score" && Array.isArray(result.hireable)) {
    return result.hireable
      .filter((entry) => ((entry as { flags: string[] }).flags ?? []).length > 0)
      .map((entry) => String((entry as { provider_id: string }).provider_id));
  }
  return [];
}

// A node and everything one edge away from it, in blue
export function neighbourhoodOf(snapshot: Snapshot | null, id: string): Highlight {
  const focus = new Set([id]);
  for (const edge of snapshot?.edges ?? []) {
    if (edge.source === id) focus.add(edge.target);
    if (edge.target === id) focus.add(edge.source);
  }
  return { focus, alert: new Set() };
}

// Every caught ring and its MEMBER nodes, tinted orange without dimming the rest
export function ringTint(snapshot: Snapshot | null): Highlight {
  const rings = new Set(snapshot?.nodes.filter((node) => node.labels.includes("Ring")).map((node) => node.id));
  const alert = new Set(rings);
  for (const edge of snapshot?.edges ?? []) {
    if (edge.type === "MEMBER" && rings.has(edge.target)) alert.add(edge.source);
    if (edge.type === "MEMBER" && rings.has(edge.source)) alert.add(edge.target);
  }
  return { focus: new Set(), alert, tintOnly: true };
}

// The graph highlight for a run: blue for the latest step, orange for everything found suspicious
export function runHighlight(run: RunState, selected?: ToolStep): Highlight {
  const steps = run.jobs.flatMap((job) => job.steps).filter((step) => step.ok !== undefined);
  const latest = selected ?? steps[steps.length - 1];
  const alert = new Set(steps.flatMap(alertsOf));
  const focus = new Set(latest ? focusOf(latest) : []);
  if (latest) focus.add(run.buyerId);
  for (const id of alert) focus.delete(id);
  return { focus, alert };
}
