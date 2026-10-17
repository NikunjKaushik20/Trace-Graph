import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { GuardMode, Health } from "../api/types";
import { GUARD_WORDS } from "../graph/names";
import "./unplug.css";

interface Props {
  health: Health | null;
  reachable: boolean;
  onChange: () => void;
}

const GUARDS: [GuardMode, string][] = [
  ["closed", "Fleet only"],
  ["open", "Funding check"],
  ["unguarded", "No guard"],
];

const OPERATOR = new URLSearchParams(window.location.search).has("operator");

// The token for the admin routes, kept for this tab only
function savedToken(): string {
  try {
    return sessionStorage.getItem("admin-token") ?? "";
  } catch {
    return "";
  }
}

// No graph, no payment: the database's state, and the operator's switches for the live demo
export function UnplugSection({ health, reachable, onChange }: Props) {
  const [token, setToken] = useState(savedToken);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const up = reachable && health?.falkordb === "up" && !health.unplugged;

  // Calls one admin route and reports how it went
  async function operate(route: string, body: unknown, done: string): Promise<void> {
    setBusy(true);
    setMessage(null);
    try {
      sessionStorage.setItem("admin-token", token);
    } catch {
      setMessage(null);
    }
    try {
      await api.admin(route, token, body);
      setMessage(done);
      onChange();
    } catch (failure) {
      setMessage(failure instanceof ApiError ? failure.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="band band-white" id="unplug" aria-labelledby="unplug-title">
      <header className="statement">
        <h2 id="unplug-title">No graph, no payment.</h2>
        <p className="statement-lede">
          Evidence, decisions, payments, policies and lessons live only in FalkorDB. Every tool reads it at the moment
          it acts, so when the database goes away the agent does not guess from memory. It refuses to pay.
        </p>
      </header>
      <div className={`unplug-state ${up ? "" : "is-down"}`} aria-live="polite">
        <p className="unplug-word">{up ? "Payments allowed." : "Payments refused."}</p>
        <p className="unplug-detail">
          {up
            ? "FalkorDB is up, and every hire waits for a fresh ranking from the graph."
            : "FalkorDB is unreachable. No tool can score, hire or pay until it is back."}
        </p>
        {health && (
          <p className="label-small tabular">
            Guard: {GUARD_WORDS[health.guard_mode] ?? health.guard_mode} ·{" "}
            {health.scorer === "udf" ? "scored inside FalkorDB" : "scored in Python"} · language model{" "}
            {health.llm_mode}
          </p>
        )}
      </div>

      {OPERATOR && (
        <details className="operator disclosure">
          <summary>Operator controls for the live demo</summary>
          <div className="operator-body">
            <label className="operator-token">
              <span className="label-small">Admin token</span>
              <input
                className="field"
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
            </label>
            <div className="operator-actions">
              <button
                type="button"
                className="pill pill-outline"
                disabled={busy || !token}
                onClick={() => operate("plug", { connected: Boolean(health?.unplugged) }, health?.unplugged ? "FalkorDB plugged back in." : "FalkorDB unplugged.")}
              >
                {health?.unplugged ? "Plug FalkorDB back in" : "Pull the plug"}
              </button>
              <div className="segmented" role="group" aria-label="Write guard">
                {GUARDS.map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    aria-pressed={health?.guard_mode === mode}
                    disabled={busy || !token}
                    onClick={() => operate("guard", { mode }, `Guard set to ${label.toLowerCase()}.`)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button type="button" className="pill pill-outline" disabled={busy || !token} onClick={() => operate("ring", {}, "The ring arrived.")}>
                Bring in the ring
              </button>
              <button
                type="button"
                className="pill pill-outline"
                disabled={busy || !token}
                onClick={() => operate("seed", { with_ring: false }, "Fresh market seeded.")}
              >
                Reseed the market
              </button>
            </div>
            {message && <p className="notice">{message}</p>}
          </div>
        </details>
      )}
    </section>
  );
}
