import type { Scoreboard } from "../../api/types";

const LANE_NAMES: Record<string, string> = {
  alone: "Alone",
  together: "Together",
  poisoned: "Poisoned",
  guarded: "Guarded",
  guarded_half_hidden: "Guarded, half the funding hidden",
  quarantine: "Half hidden, ring quarantined",
  bad_mouthed: "Bad-mouthed",
};

interface Props {
  board: Scoreboard | null;
  missing: boolean;
}

// The 100-seed scoreboard per lane and adversary once it is stored, and the limits either way
export function ScoreboardTable({ board, missing }: Props) {
  return (
    <div className="scoreboard">
      <h3>{board || !missing ? "All 100 seeds" : "What the guard does not cover"}</h3>
      {board ? (
        <table className="ranking">
          <thead>
            <tr>
              <th scope="col">Lane</th>
              <th scope="col">Adversary</th>
              <th scope="col" className="is-number">
                Mean
              </th>
              <th scope="col" className="is-number">
                Median
              </th>
              <th scope="col" className="is-number">
                p90
              </th>
            </tr>
          </thead>
          <tbody>
            {board.lanes.map((lane) => (
              <tr key={lane.lane + lane.adversary}>
                <th scope="row">{LANE_NAMES[lane.lane] ?? lane.lane}</th>
                <td>{lane.adversary}</td>
                <td className="is-number tabular">{lane.mean.toFixed(1)}</td>
                <td className="is-number tabular">{lane.median.toFixed(1)}</td>
                <td className="is-number tabular">{lane.p90.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        !missing && <p className="notice">Reading the scoreboard…</p>
      )}
      <p className="notice scoreboard-limits">
        Two harder attacks are in the scoreboard so their cost is measured, not guessed: Sybils that report fake
        failures to sink honest providers, and Sybils that hide half their funding links so no path reaches the
        provider. One attack is not covered at all: an admitted buyer that lies about its own jobs.
      </p>
    </div>
  );
}
