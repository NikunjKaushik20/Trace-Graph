import { useMemo } from "react";
import { ringTint } from "../agent/highlights";
import type { Health, Snapshot, Spend } from "../api/types";
import { GraphCanvas } from "../graph/GraphCanvas";
import "./hero.css";

interface Props {
  snapshot: Snapshot | null;
  error: string | null;
  onRetry: () => void;
  health: Health | null;
  spend: Spend | null;
}

// Counts the nodes of each kind worth naming in the hero callout
function census(snapshot: Snapshot) {
  const has = (label: string) => snapshot.nodes.filter((node) => node.labels.includes(label)).length;
  return { buyers: has("Buyer"), providers: has("Provider"), payments: has("Payment"), rings: has("Ring") };
}

// The opening: the live market graph is the product shot, with the claim above it
export function Hero({ snapshot, error, onRetry, health, spend }: Props) {
  const counts = snapshot ? census(snapshot) : null;
  const tint = useMemo(() => ringTint(snapshot), [snapshot]);
  return (
    <section className="hero" id="top">
      <h1 className="hero-title">Agents that check the graph before they pay.</h1>
      <p className="hero-sub">
        Five buyer agents hire and pay other agents. They share one FalkorDB graph of who paid whom, who reviewed whom
        and who funds whom, and every payment waits for that graph to say yes.
      </p>
      <div className="hero-actions">
        <a className="pill pill-blue pill-large" href="#agent">
          Run the agent
        </a>
        <a className="text-link" href="#proof">
          See the proof
        </a>
      </div>
      <div className="hero-stage">
        <GraphCanvas
          snapshot={snapshot}
          highlight={tint}
          labels
          stretch={1.9}
          reserveBottom={130}
          ariaLabel="The live market graph in FalkorDB: buyers, providers, payments, reviews and funding"
        />
        <aside className="hero-callout" aria-live="polite">
          {counts && snapshot ? (
            <>
              <strong className="tabular">
                {snapshot.nodes.length} nodes · {snapshot.edges.length} edges
              </strong>
              <span>
                {counts.buyers} buyers, {counts.providers} providers and {counts.payments} payments, read live from
                FalkorDB in {Math.round(snapshot.graph_ms)} ms.{" "}
                {counts.rings > 0 && (
                  <span className="hero-ring-note">
                    {counts.rings === 1 ? "One ring caught" : `${counts.rings} rings caught`} and quarantined.
                  </span>
                )}
              </span>
            </>
          ) : error ? (
            <>
              <strong>The graph could not be read</strong>
              <span>
                {error}{" "}
                <button type="button" className="text-link" onClick={onRetry}>
                  Try again
                </button>
              </span>
            </>
          ) : (
            <>
              <strong>Reading the graph</strong>
              <span>Connecting to FalkorDB…</span>
            </>
          )}
          {health && spend && (
            <span className="hero-callout-meta tabular">
              Scored inside FalkorDB · language model spend ${spend.usd.toFixed(2)} of ${spend.limit_usd.toFixed(2)}
            </span>
          )}
        </aside>
      </div>
    </section>
  );
}
