import { resultOf, type RunState, type ToolStep } from "../../agent/steps";
import { api } from "../../api/client";

export interface RingFacts {
  ringId: string;
  providers: string[];
  writers: string[];
  wallets: string[];
  hub: string;
  bridge?: string;
  outsidePraise?: number;
  communitySize?: number;
  path: string[];
  policyId?: string;
}

// The newest finished step with a given tool name
function lastStep(run: RunState, name: string, accept: (step: ToolStep) => boolean = () => true) {
  const steps = run.jobs.flatMap((job) => job.steps).filter((step) => step.name === name && step.ok && accept(step));
  return steps[steps.length - 1];
}

// Reads the ring straight from the agent's own find_ring, funding_path and quarantine results
export function factsFromRun(run: RunState): RingFacts | null {
  const ring = lastStep(run, "find_ring", (step) => Boolean(resultOf(step).is_ring));
  if (!ring) return null;
  const found = resultOf(ring);
  const path = lastStep(run, "funding_path", (step) => Boolean(resultOf(step).found));
  const policy = lastStep(run, "quarantine");
  return {
    ringId: String(found.ring_id),
    providers: found.providers as string[],
    writers: found.writers as string[],
    wallets: found.wallets as string[],
    hub: String(found.hub_funder),
    bridge: found.bridge_wallet ? String(found.bridge_wallet) : undefined,
    outsidePraise: Number(found.reports_from_outside_writers),
    communitySize: Number(found.praise_community_size),
    path: path ? (resultOf(path).path as string[]) : [],
    policyId: policy ? String(resultOf(policy).policy_id) : undefined,
  };
}

// Rebuilds the ring from a quarantine already in the graph, for visitors who arrive after the run
export async function factsFromGraph(): Promise<RingFacts | null> {
  const { policies } = await api.quarantines();
  const policy = policies[policies.length - 1];
  if (!policy?.decision_id) return null;
  const [receipt, funding] = await Promise.all([api.receipt(policy.decision_id), api.funding(policy.covered[0])]);
  const funded = funding.shared_funders.flatMap((funder) => funder.also_funds);
  const path = receipt.funding_traces[0]?.node_ids ?? [];
  const hub = path.find((id) => id.startsWith("root-")) ?? policy.covered[0];
  return {
    ringId: receipt.rings[0] ?? policy.policy_id,
    providers: policy.covered,
    writers: [...new Set([...path, ...funded].filter((id) => id.startsWith("sybil-")))].sort(),
    wallets: path.filter((id) => id.startsWith("wallet-") || id.startsWith("root-")),
    hub,
    path,
    policyId: policy.policy_id,
  };
}
