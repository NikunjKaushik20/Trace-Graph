import { useMemo, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Answer, Snapshot } from "../../api/types";
import { GraphCanvas } from "../../graph/GraphCanvas";
import "./ask.css";

const QUESTIONS = [
  "Who funds prov-quickdigest, and why was it quarantined?",
  "Why was the last refund refunded?",
  "Who authorised the most recent payment?",
];

// The part of the market an answer walked through: its path ids and the edges between them
function pathGraph(snapshot: Snapshot | null, ids: string[]): Snapshot | null {
  if (!snapshot || ids.length === 0) return null;
  const wanted = new Set(ids);
  const nodes = snapshot.nodes.filter((node) => wanted.has(node.id));
  const kept = new Set(nodes.map((node) => node.id));
  const edges = snapshot.edges.filter((edge) => kept.has(edge.source) && kept.has(edge.target));
  return { ...snapshot, nodes, edges };
}

// Ask the graph: a visitor's question answered by the read-only investigator, with the path drawn
export function AskSection({ snapshot }: { snapshot: Snapshot | null }) {
  const [question, setQuestion] = useState(QUESTIONS[0]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = useMemo(() => pathGraph(snapshot, answer?.path_ids ?? []), [snapshot, answer]);
  const highlight = useMemo(() => ({ focus: new Set(answer?.path_ids ?? []), alert: new Set<string>() }), [answer]);

  // Sends the question and shows the answer, or why there is none
  async function ask(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (asking || question.trim().length < 3) return;
    setAsking(true);
    setError(null);
    try {
      setAnswer(await api.ask(question.trim()));
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "The investigator could not answer.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <section className="band band-mist" id="ask" aria-labelledby="ask-title">
      <div className="band-head is-quiet">
        <div>
          <h2 id="ask-title">Ask the graph.</h2>
          <p className="band-lede">
            The investigator answers through eight read-only tools over the same graph, so a question can never move
            money. Every id in its answer is checked against FalkorDB before you see it.
          </p>
        </div>
      </div>
      <div className="ask card">
        <form className="ask-form" onSubmit={ask}>
          <label className="visually-hidden" htmlFor="question">
            Your question
          </label>
          <input
            id="question"
            className="field"
            maxLength={500}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button type="submit" className="pill pill-blue pill-large" disabled={asking}>
            {asking ? "Asking…" : "Ask"}
          </button>
        </form>
        <div className="ask-suggestions">
          {QUESTIONS.map((suggestion) => (
            <button key={suggestion} type="button" className="text-link" onClick={() => setQuestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
        {error && <p className="notice is-error">{error}</p>}
        {answer && (
          <div className="ask-answer">
            <div>
              <p className="ask-text">{answer.answer}</p>
              <p className="label-small ask-tools">
                {answer.tools.map((tool) => (
                  <code key={tool.name + JSON.stringify(tool.arguments)} className={tool.ok ? "" : "is-orange"}>
                    {tool.name}
                  </code>
                ))}
              </p>
              <p className="label-small">
                {answer.citations_passed ? "Every id it cites is in the graph" : "It cited an id the graph does not have"}
                {" · "}
                {answer.questions_left} questions left for this browser
              </p>
            </div>
            <div className="ask-graph">
              {path && path.nodes.length > 0 ? (
                <GraphCanvas snapshot={path} highlight={highlight} labels ariaLabel="The nodes the answer walked through" />
              ) : (
                <p className="notice">The answer did not walk through any node in the market view.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
