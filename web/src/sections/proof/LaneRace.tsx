import { useEffect, useState } from "react";
import { ApiError, playLane } from "../../api/client";
import type { Adversary, RoundResult } from "../../api/types";
import { raceVerdict } from "./raceVerdict";

const RACE = [
  ["alone", "Alone", "Each buyer keeps its own records"],
  ["together", "Together", "One shared graph, no attack"],
  ["poisoned", "Poisoned", "20 Sybils praise a ring, no guard"],
  ["guarded", "Guarded", "Same attack, funding check on"],
] as const;

const HEATS = [RACE.slice(0, 2), RACE.slice(2, 4)];
const ROUNDS = 60;

type Lane = (typeof RACE)[number][0];

// The words under a lane's number: waiting, next heat, or how far it has got
function laneStatus(round: RoundResult | undefined, heat: number, playingHeat: number | null): string {
  if (round) return `round ${round.round} of ${ROUNDS} · ${round.malicious_jobs} bad jobs`;
  if (playingHeat !== null && heat > playingHeat) return "next heat";
  return "sats lost";
}

// Four markets on one seed, played round by round in FalkorDB, in two heats of two
export function LaneRace({ demoSeed }: { demoSeed?: number | null }) {
  const [seed, setSeed] = useState(demoSeed ?? 1000);
  useEffect(() => {
    if (demoSeed) setSeed(demoSeed);
  }, [demoSeed]);
  const [adversary, setAdversary] = useState<Adversary>("strat");
  const [rounds, setRounds] = useState<Partial<Record<Lane, RoundResult>>>({});
  const [playingHeat, setPlayingHeat] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const verdict = raceVerdict(rounds, ROUNDS);

  // Plays the heats one after the other; the API runs at most two markets at once
  async function race(): Promise<void> {
    setError(null);
    setRounds({});
    try {
      for (const [index, heat] of HEATS.entries()) {
        setPlayingHeat(index);
        await Promise.all(
          heat.map(([lane]) =>
            playLane(lane, seed, adversary, (round) => setRounds((before) => ({ ...before, [lane]: round }))),
          ),
        );
      }
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "The race stopped early. Play it again to restart.");
    } finally {
      setPlayingHeat(null);
    }
  }

  const running = playingHeat !== null;
  return (
    <div className="race">
      <header className="race-head">
        <div>
          <h3>One seed, four markets, played live.</h3>
          <p className="notice">
            Five buyers, sixty rounds, the TRACE paper's market contract, played inside FalkorDB. The counter is sats
            lost to providers that take the money and fail.
          </p>
          <p className="notice">
            {demoSeed
              ? `Seed ${demoSeed} is picked by rule: its Alone minus Together gap is the closest to the median of all 100.`
              : "One seed; the scoreboard has all 100."}
          </p>
        </div>
        <div className="race-controls">
          <label className="race-seed">
            <span className="label-small">Seed, 1000 to 1099</span>
            <input
              className="field"
              type="number"
              min={1000}
              max={1099}
              value={seed}
              disabled={running}
              onChange={(event) => setSeed(Math.min(1099, Math.max(1000, Number(event.target.value) || 1000)))}
            />
          </label>
          <div className="segmented" role="group" aria-label="How the providers cheat">
            {(["strat", "calib"] as const).map((name) => (
              <button
                key={name}
                type="button"
                disabled={running}
                aria-pressed={adversary === name}
                onClick={() => setAdversary(name)}
              >
                {name === "strat" ? "Strategic cheats" : "Calibrated cheats"}
              </button>
            ))}
          </div>
          <button type="button" className="pill pill-blue" disabled={running} onClick={race}>
            {running ? `Playing heat ${(playingHeat ?? 0) + 1} of 2…` : verdict ? "Play again" : "Play the race"}
          </button>
        </div>
      </header>
      <div className="race-lanes">
        {HEATS.flatMap((heat, heatIndex) =>
          heat.map(([lane, title, line]) => {
            const round = rounds[lane];
            const tone = round && lane === "poisoned" ? "is-orange" : round && lane === "guarded" ? "is-blue" : "";
            return (
              <article key={lane} className={`race-lane ${round ? "" : "is-idle"}`}>
                <h4>{title}</h4>
                <p className="race-lane-line">{line}</p>
                <p className={`race-number tabular ${tone}`}>{round ? round.fraud_sats : 0}</p>
                <p className="label-small tabular">{laneStatus(round, heatIndex, playingHeat)}</p>
                <span className="race-progress" aria-hidden="true">
                  <i style={{ transform: `scaleX(${(round?.round ?? 0) / ROUNDS})` }} />
                </span>
              </article>
            );
          }),
        )}
      </div>
      <p className="race-verdict" aria-live="polite">
        {verdict ??
          (running ? "" : "Press play. Each lane is a real market replayed in the graph, about eight seconds a heat.")}
      </p>
      {error && <p className="notice is-error">{error}</p>}
    </div>
  );
}
