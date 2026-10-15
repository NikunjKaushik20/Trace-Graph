import type { Health } from "../api/types";
import "./nav.css";

const ANCHORS = [
  ["agent", "Agent"],
  ["rings", "Rings"],
  ["receipts", "Receipts"],
  ["proof", "Proof"],
  ["ask", "Ask"],
  ["unplug", "Unplug"],
] as const;

interface Props {
  health: Health | null;
  reachable: boolean;
}

// The database's state in two words, for the nav
function databaseWord(health: Health | null, reachable: boolean): [string, string] {
  if (!reachable) return ["API offline", "is-orange"];
  if (!health) return ["Connecting", "is-slate"];
  if (health.unplugged) return ["FalkorDB unplugged", "is-orange"];
  return health.falkordb === "up" ? ["FalkorDB live", "is-ink"] : ["FalkorDB down", "is-orange"];
}

// The sticky product bar with section links, the database state and the main action
export function Nav({ health, reachable }: Props) {
  const [word, tone] = databaseWord(health, reachable);
  return (
    <nav className="local-nav" aria-label="Sections">
      <a className="local-nav-title" href="#top">
        TRACE-Graph
      </a>
      <div className="local-nav-links">
        {ANCHORS.map(([id, label]) => (
          <a key={id} href={`#${id}`}>
            {label}
          </a>
        ))}
      </div>
      <div className="local-nav-actions">
        <span className={`status-word ${tone}`}>
          <span className={`status-dot ${tone}`} aria-hidden="true" />
          {word}
        </span>
        <a className="pill pill-blue" href="#agent">
          Run the agent
        </a>
      </div>
    </nav>
  );
}
