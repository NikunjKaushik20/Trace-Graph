import { api } from "../../api/client";
import type { AgentEval, Scoreboard } from "../../api/types";
import { useResource } from "../../hooks/useLive";
import { LaneRace } from "./LaneRace";
import { ScoreboardTable } from "./ScoreboardTable";
import "./proof.css";

// The two agent lanes head to head: same model, with FalkorDB tools and with plain text
function EvalFigures({ result }: { result: AgentEval }) {
  const graph = result.lanes.find((lane) => lane.lane === "graph");
  const text = result.lanes.find((lane) => lane.lane === "text");
  if (!graph || !text) return null;
  const run = result.run;
  return (
    <>
      <div className="proof-duel">
        <figure>
          <figcaption>With the FalkorDB tools</figcaption>
          <p className="proof-number tabular">{graph.scams_hired}</p>
          <p className="proof-caption tabular">
            scams hired out of {graph.cases}, {graph.sats_to_scams} sats lost
          </p>
        </figure>
        <figure>
          <figcaption>Reading the reviews as text</figcaption>
          <p className="proof-number tabular is-orange">{text.scams_hired}</p>
          <p className="proof-caption tabular">
            scams hired out of {text.cases}, {text.sats_to_scams} sats lost
          </p>
        </figure>
      </div>
      <table className="proof-tools">
        <caption>How the graph lane chose its tools</caption>
        <tbody>
          <tr>
            <th scope="row">Rings it investigated</th>
            <td className="tabular">
              {run.rings_investigated} of {run.ring_cases}
            </td>
          </tr>
          <tr>
            <th scope="row">Quarantines backed by a traced funding path</th>
            <td className="tabular">
              {run.quarantines_backed} of {run.quarantines}, {run.false_quarantines} false
            </td>
          </tr>
          <tr>
            <th scope="row">Summaries that cite only ids in the graph</th>
            <td className="tabular">{Math.round(run.citation_pass_rate * 100)}%</td>
          </tr>
          <tr>
            <th scope="row">Investigations aimed at a real ring</th>
            <td className="tabular">
              {Math.round(run.precision * 100)}%; the rest checked close calls and new providers, which costs a tool
              call and no money
            </td>
          </tr>
        </tbody>
      </table>
    </>
  );
}

// Proof, not vibes: the agent eval, a live race on one seed, and the 100-seed scoreboard
export function ProofSection() {
  const evaluation = useResource<AgentEval>(() => api.agentEval());
  const board = useResource<Scoreboard>(() => api.scoreboard());
  return (
    <section className="band band-white" id="proof" aria-labelledby="proof-title">
      <header className="statement">
        <h2 id="proof-title">Same model. With and without the graph.</h2>
        <p className="statement-lede">
            {evaluation.data
              ? `${evaluation.data.run.cases} hiring cases, ${evaluation.data.run.ring_cases} of them Sybil rings, run twice with ${evaluation.data.run.model}. `
              : ""}
          One lane calls the FalkorDB tools. The other reads every provider's reviews as plain text.
        </p>
      </header>
      {evaluation.data && <EvalFigures result={evaluation.data} />}
      {evaluation.error && <p className="notice">{evaluation.error.message}</p>}

      <LaneRace demoSeed={board.data?.demo_seed} />
      <ScoreboardTable board={board.data} missing={board.error?.status === 404} />
    </section>
  );
}
