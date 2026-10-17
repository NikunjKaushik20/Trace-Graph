import type { RoundResult } from "../../api/types";

type Finished = Record<"alone" | "together" | "poisoned" | "guarded", RoundResult>;

// Within a few sats, or within 5% of the larger number, counts as level
function level(a: number, b: number): boolean {
  return Math.abs(a - b) <= Math.max(5, 0.05 * Math.max(a, b));
}

// What sharing the graph did on this seed, in one sentence
function sharingLine({ alone, together }: Finished): string {
  if (level(alone.fraud_sats, together.fraud_sats)) {
    return `Sharing one graph changed little on this seed: ${alone.fraud_sats} sats lost alone, ${together.fraud_sats} together.`;
  }
  if (together.fraud_sats < alone.fraud_sats) {
    return `Sharing one graph cut the losses from ${alone.fraud_sats} sats to ${together.fraud_sats}.`;
  }
  return `On this seed sharing cost more than it saved: ${alone.fraud_sats} sats alone, ${together.fraud_sats} together.`;
}

// What the ring and the funding check did on this seed, in one sentence
function ringLine({ together, poisoned, guarded }: Finished): string {
  const added = poisoned.fraud_sats - together.fraud_sats;
  const saved = poisoned.fraud_sats - guarded.fraud_sats;
  if (level(poisoned.fraud_sats, guarded.fraud_sats) && added <= Math.max(5, 0.05 * together.fraud_sats)) {
    return "The ring got nowhere: TRACE's own scoring kept it out, so the funding check had nothing left to stop.";
  }
  if (saved > 0) {
    return `The ring added ${added} sats of losses, and the funding check took ${saved} of them back.`;
  }
  return `The ring added ${added} sats of losses, and the funding check did not stop it on this seed.`;
}

// The two-sentence reading of a finished race, or null while any lane is still running
export function raceVerdict(rounds: Partial<Finished>, totalRounds: number): string | null {
  const lanes = [rounds.alone, rounds.together, rounds.poisoned, rounds.guarded];
  if (lanes.some((round) => !round || round.round < totalRounds)) return null;
  const finished = rounds as Finished;
  return `${sharingLine(finished)} ${ringLine(finished)}`;
}
