import { useEffect, useMemo, useState } from "react";
import { neighbourhoodOf, runHighlight } from "../../agent/highlights";
import type { RunState, ToolStep } from "../../agent/steps";
import type { Snapshot, View } from "../../api/types";
import { GraphCanvas } from "../../graph/GraphCanvas";
import { useSnapshot } from "../../hooks/useLive";
import { JobLedger } from "./JobLedger";
import { ToolTrace } from "./ToolTrace";
import "./agent.css";

const EXAMPLES = [
  ["Summarise and tag", "Summarise this and pull out the keywords: FalkorDB keeps a property graph in sparse adjacency matrices, so an agent can run a multi-hop Cypher query on every decision and still answer in milliseconds."],
  ["Translate", "Translate into French: The payment stays in escrow until the judge accepts the work."],
  ["Summarise", "Summarise: Sybil rings fake trust. A handful of wallets fund dozens of reviewers who praise the ring's own services, so a buyer that only counts stars pays the ring."],
];

const BUYERS = ["buyer-1", "buyer-2", "buyer-3", "buyer-4", "buyer-5"];

interface Props {
  snapshot: Snapshot | null;
  run: RunState;
  onStart: (buyerId: string, text: string, view: View) => void;
  onShowReceipt: (decisionId: string) => void;
}

// The live console: give a buyer agent a task, watch its tool calls and the graph it reads
export function AgentSection({ snapshot, run, onStart, onShowReceipt }: Props) {
  const [buyerId, setBuyerId] = useState("buyer-1");
  const [view, setView] = useState<View>("together");
  const [text, setText] = useState(EXAMPLES[0][1]);
  const [selected, setSelected] = useState<ToolStep | undefined>();
  const busy = run.status === "starting" || run.status === "running";
  const own = useSnapshot("alone", buyerId, view === "alone");
  const shown = view === "alone" ? own.snapshot : snapshot;
  const started = run.jobs.some((job) => job.steps.length > 0);
  const highlight = useMemo(
    () => (started ? runHighlight(run, selected) : neighbourhoodOf(shown, buyerId)),
    [started, run, selected, shown, buyerId],
  );
  const stepCount = run.jobs.reduce((total, job) => total + job.steps.length, 0);
  const reloadOwn = own.reload;

  useEffect(() => {
    if (view === "alone") reloadOwn();
  }, [view, stepCount, reloadOwn]);

  // Sends the task, clearing any step the visitor had pinned
  function submit(event: React.FormEvent): void {
    event.preventDefault();
    if (busy || text.trim().length < 3) return;
    setSelected(undefined);
    onStart(buyerId, text.trim(), view);
  }

  return (
    <section className="band band-mist" id="agent" aria-labelledby="agent-title">
      <div className="band-head">
        <div>
          <h2 id="agent-title">Watch an agent decide.</h2>
          <p className="band-lede">
            Give a buyer a task. It splits the task into jobs, reads the shared graph, scores every provider with TRACE
            inside FalkorDB, follows the money when something looks off, and only then pays into escrow.
          </p>
        </div>
        <a className="text-link" href="#rings">
          What it does with a ring
        </a>
      </div>

      <div className="card console">
        <form className="console-task" onSubmit={submit}>
          <div className="console-switches">
            <div className="segmented" role="group" aria-label="Buyer agent">
              {BUYERS.map((buyer) => (
                <button key={buyer} type="button" aria-pressed={buyer === buyerId} onClick={() => setBuyerId(buyer)}>
                  <span className="buyer-word">Buyer </span>
                  {buyer.slice(-1)}
                </button>
              ))}
            </div>
            <div className="segmented" role="group" aria-label="What the buyer can read">
              <button type="button" aria-pressed={view === "together"} onClick={() => setView("together")}>
                Shared graph
              </button>
              <button type="button" aria-pressed={view === "alone"} onClick={() => setView("alone")}>
                Its own records only
              </button>
            </div>
          </div>
          <label className="visually-hidden" htmlFor="task-text">
            Task for the buyer agent
          </label>
          <div className="console-input">
            <textarea
              id="task-text"
              className="field console-field"
              rows={2}
              maxLength={2000}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <button className="pill pill-blue pill-large" type="submit" disabled={busy}>
              {busy ? "Working…" : "Run task"}
            </button>
          </div>
          <div className="console-examples">
            <span className="console-hint">Jobs it can buy: summarise, extract keywords, translate into French.</span>
            {EXAMPLES.map(([name, example]) => (
              <button key={name} type="button" className="text-link" onClick={() => setText(example)}>
                {name}
              </button>
            ))}
          </div>
        </form>

        <div className="console-body">
          <ToolTrace run={run} selected={selected} onSelect={setSelected} />
          <div className="console-graph">
            <GraphCanvas
              snapshot={shown}
              highlight={highlight}
              interactive
              ariaLabel="The shared market graph, with the nodes the agent is using highlighted"
            />
            <ul className="legend" aria-label="Legend">
              <li>
                <i className="swatch is-blue" /> What the agent is reading now
              </li>
              <li>
                <i className="swatch is-orange" /> Flagged, ring or refunded
              </li>
              <li>
                <i className="swatch is-hollow" /> Wallets and ignored claims
              </li>
              <li className="legend-hint">
                {view === "alone" ? `Only ${buyerId}'s own records` : "Drag to pan, scroll to zoom, double-click to fit"}
              </li>
            </ul>
          </div>
        </div>

        <JobLedger run={run} onShowReceipt={onShowReceipt} />
      </div>
    </section>
  );
}
