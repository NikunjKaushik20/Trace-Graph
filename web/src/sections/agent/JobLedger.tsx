import type { JobRun, RunState } from "../../agent/steps";
import { useNameOf } from "../../graph/names";

const ID_PATTERN =
  /\b((?:prov|buyer|sybil|writer|dec|job|pay|policy|ring|lesson|task|root|wallet|principal)-[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9])/g;

interface Props {
  run: RunState;
  onShowReceipt: (decisionId: string) => void;
}

// The narration with every cited id set as code, and decision ids as links to their receipts
function Narration({ text, onShowReceipt }: { text: string; onShowReceipt: (id: string) => void }) {
  const parts = text.split(ID_PATTERN);
  const nameOf = useNameOf();
  return (
    <p className="ledger-narration">
      {parts.map((part, index) => {
        if (index % 2 === 0) return part;
        if (part.startsWith("dec-")) {
          return (
            <button key={index} type="button" className="ledger-id is-link" onClick={() => onShowReceipt(part)}>
              {part}
            </button>
          );
        }
        return (
          <code key={index} className="ledger-id" title={part}>
            {nameOf(part)}
          </code>
        );
      })}
    </p>
  );
}

// The escrow for one job: held, then released or refunded
function EscrowLine({ job }: { job: JobRun }) {
  const { escrow } = job;
  if (!escrow) return <span className="ledger-escrow is-slate">No payment yet</span>;
  const tone = escrow.status === "refunded" ? "is-orange" : escrow.status === "held" ? "is-blue" : "is-ink";
  const word = { held: "Held in escrow", released: "Released", refunded: "Refunded" }[escrow.status];
  return (
    <span className="ledger-escrow">
      <span className={`status-word ${tone}`}>{word}</span>
      <span className="tabular">
        {escrow.sats} sats to {escrow.providerName ?? escrow.providerId}
      </span>
      {escrow.judgeReason && <span className="is-slate">Judge: {escrow.judgeReason}</span>}
    </span>
  );
}

// One row per job: where its money is, what the agent said, and the receipts behind it
export function JobLedger({ run, onShowReceipt }: Props) {
  if (run.jobs.length === 0) return null;
  return (
    <div className="ledger">
      {run.jobs.map((job) => (
        <article key={job.job.job_id} className="ledger-job">
          <header>
            <h3>{job.job.capability.replace("_", " ")}</h3>
            <EscrowLine job={job} />
          </header>
          {job.narration ? (
            <Narration text={job.narration} onShowReceipt={onShowReceipt} />
          ) : (
            <p className="ledger-narration is-slate">{job.error ?? "The agent explains itself when the job ends."}</p>
          )}
          <footer>
            {job.decisionIds.map((decisionId) => (
              <button key={decisionId} type="button" className="text-link" onClick={() => onShowReceipt(decisionId)}>
                Receipt for {decisionId}
              </button>
            ))}
            {job.citations && (
              <span className={job.citations.unknown.length === 0 ? "label-small" : "label-small is-orange"}>
                {job.citations.unknown.length === 0
                  ? `All ${job.citations.cited.length} ids it cites are in the graph`
                  : `Unknown ids: ${job.citations.unknown.join(", ")}`}
              </span>
            )}
          </footer>
        </article>
      ))}
    </div>
  );
}
