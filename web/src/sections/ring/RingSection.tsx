import { useEffect, useMemo, useState } from "react";
import type { RunState } from "../../agent/steps";
import { api } from "../../api/client";
import type { Snapshot } from "../../api/types";
import type { Highlight } from "../../graph/draw";
import { GraphCanvas } from "../../graph/GraphCanvas";
import { factsFromGraph, factsFromRun, type RingFacts } from "./ringFacts";
import { RING_STEPS, RingSteps } from "./RingSteps";
import "./ring.css";

interface Props {
  run: RunState;
  snapshot: Snapshot | null;
}

// The ring pulled out of the market: the hub's two-hop neighbourhood
function useRingGraph(facts: RingFacts | null): Snapshot | null {
  const [ring, setRing] = useState<Snapshot | null>(null);
  useEffect(() => {
    if (!facts) return;
    api
      .neighbourhood(facts.hub)
      .then((found) => setRing({ ...found, graph: "market" }))
      .catch(() => setRing(null));
  }, [facts?.hub]);
  return ring;
}

// The whole ring at once: the path in blue, everything else in it orange
function wholeRing(facts: RingFacts | null): Highlight {
  if (!facts) return { focus: new Set(), alert: new Set() };
  const alert = new Set([...facts.providers, ...facts.writers, ...facts.wallets, facts.ringId]);
  const focus = new Set(facts.path);
  for (const id of focus) alert.delete(id);
  return { focus, alert };
}

// Too good to be true: how the agent catches a Sybil ring with graph algorithms and blocks it
export function RingSection({ run, snapshot }: Props) {
  const fromRun = useMemo(() => factsFromRun(run), [run]);
  const [fromGraph, setFromGraph] = useState<RingFacts | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const facts = fromRun ?? fromGraph;
  const ringGraph = useRingGraph(facts);

  useEffect(() => {
    if (!fromRun) factsFromGraph().then(setFromGraph, () => setFromGraph(null));
  }, [fromRun, snapshot?.nodes.length]);

  const highlight = useMemo<Highlight>(
    () => (facts && active !== null ? RING_STEPS[active].lights(facts) : wholeRing(facts)),
    [facts, active],
  );

  return (
    <section className="band band-white ring" id="rings" aria-labelledby="rings-title">
      <header className="statement">
        <h2 id="rings-title">Too good to be true.</h2>
        <p className="statement-lede">
          A cheap provider shows up with twenty fresh five-star reviews. A buyer that counts stars would hire it. The
          agent asks the graph who paid for the praise.
        </p>
      </header>
      <div className="ring-stage">
        <GraphCanvas
          snapshot={ringGraph}
          highlight={highlight}
          labels
          interactive
          ariaLabel="The ring the agent found: its providers, Sybil writers and funding wallets, with the funding path it followed"
        />
        {!facts && <p className="ring-wait">Run the first example in the console and the ring it finds is drawn here.</p>}
      </div>
      <RingSteps facts={facts} active={active} onActive={setActive} />
    </section>
  );
}
