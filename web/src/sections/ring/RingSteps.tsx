import type { Highlight } from "../../graph/draw";
import type { RingFacts } from "./ringFacts";

export interface RingStep {
  algorithm: string;
  does: string;
  found: (facts: RingFacts) => string;
  lights: (facts: RingFacts) => Highlight;
}

// A highlight with only blue nodes, or only orange ones
const blue = (ids: string[]): Highlight => ({ focus: new Set(ids), alert: new Set() });
const orange = (ids: string[]): Highlight => ({ focus: new Set(), alert: new Set(ids) });

export const RING_STEPS: RingStep[] = [
  {
    algorithm: "Shortest path",
    does: "Walks the money from one reviewer back to the provider it praised.",
    found: (facts) => (facts.path.length ? `${facts.path.length - 1} hops from ${facts.path[0]}` : "Not traced in this run"),
    lights: (facts) => blue(facts.path),
  },
  {
    algorithm: "WCC and label propagation",
    does: "Find the component the praise comes from, and the community inside it.",
    found: (facts) =>
      facts.outsidePraise !== undefined
        ? `${facts.outsidePraise} reports from one community of ${facts.communitySize}`
        : `${facts.writers.length} writers in one component`,
    lights: (facts) => orange(facts.writers),
  },
  {
    algorithm: "PageRank",
    does: "Names the hub wallet that pays for all of it.",
    found: (facts) => facts.hub,
    lights: (facts) => blue([facts.hub]),
  },
  {
    algorithm: "Betweenness",
    does: "Finds the wallet that carries the money across.",
    found: (facts) => facts.bridge ?? facts.wallets.filter((id) => id !== facts.hub)[0] ?? "None found",
    lights: (facts) => blue(facts.bridge ? [facts.bridge] : facts.wallets),
  },
  {
    algorithm: "Quarantine",
    does: "A policy written into FalkorDB. Every buyer skips the ring from that moment.",
    found: (facts) => (facts.policyId ? `${facts.providers.length} providers blocked` : "Not quarantined yet"),
    lights: (facts) => orange(facts.providers),
  },
];

interface Props {
  facts: RingFacts | null;
  active: number | null;
  onActive: (index: number | null) => void;
}

// The five things the agent asks the graph, in order, each lighting up what it found
export function RingSteps({ facts, active, onActive }: Props) {
  return (
    <ol className="ring-steps">
      {RING_STEPS.map((step, index) => (
        <li key={step.algorithm}>
          <button
            type="button"
            className="ring-step"
            aria-pressed={active === index}
            disabled={!facts}
            onMouseEnter={() => onActive(index)}
            onMouseLeave={() => onActive(null)}
            onFocus={() => onActive(index)}
            onBlur={() => onActive(null)}
          >
            <span className="ring-step-name">{step.algorithm}</span>
            <span className="ring-step-does">{step.does}</span>
            <span className="ring-step-found tabular">{facts ? step.found(facts) : "Waiting for a ring"}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
