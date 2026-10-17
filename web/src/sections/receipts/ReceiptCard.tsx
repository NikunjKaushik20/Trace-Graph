import type { Authorisation, Receipt } from "../../api/types";
import { GUARD_WORDS, jobTitle, useNameOf, useNamedText } from "../../graph/names";
import { RankingTable } from "./RankingTable";
import { useReceipt } from "./useReceipt";
import { flagInWords, inWords } from "./words";

interface Props {
  jobId: string | null;
  decisionId: string | null;
  version: number;
}

// The chain of ids that stands behind a payment, from the principal to the provider
function AuthorityChain({ authorisation }: { authorisation: Authorisation }) {
  const nameOf = useNameOf();
  const chain = [
    ["Principal", authorisation.principal_name],
    ["Buyer", nameOf(authorisation.buyer_id)],
    ["Task", authorisation.task_id],
    ["Job", authorisation.job_id],
    ["Decision", authorisation.decision_id],
    ["Provider", nameOf(authorisation.provider_id)],
  ];
  return (
    <ol className="chain" aria-label="Who authorised this payment">
      {chain.map(([kind, id]) => (
        <li key={kind}>
          <span className="label-small">{kind}</span>
          <code>{id}</code>
        </li>
      ))}
    </ol>
  );
}

// What the guard kept out of the score and what TRACE ruled out
function Evidence({ receipt }: { receipt: Receipt }) {
  const nameOf = useNameOf();
  return (
    <div className="receipt-evidence">
      <div>
        <h4>Counted</h4>
        <p className="tabular">{receipt.counted_jobs} settled jobs from buyers in the fleet</p>
      </div>
      <div>
        <h4>Kept, never counted</h4>
        {receipt.ignored.length === 0 ? (
          <p className="is-slate">Nothing ignored</p>
        ) : (
          receipt.ignored.map((item) => (
            <p key={item.provider_id + item.reason}>
              <span className="is-orange tabular">{item.claims} claims</span> about {nameOf(item.provider_id)},{" "}
              {inWords(item.reason)}
            </p>
          ))
        )}
      </div>
      <div>
        <h4>Ruled out</h4>
        {receipt.excluded.length === 0 ? (
          <p className="is-slate">No one</p>
        ) : (
          receipt.excluded.map((item) => (
            <p key={item.provider_id}>
              {nameOf(item.provider_id)} {inWords(item.reason)}
            </p>
          ))
        )}
      </div>
    </div>
  );
}

// One decision's receipt: ranking, guard, money traced, what-if, and the queries behind it
export function ReceiptCard({ jobId, decisionId, version }: Props) {
  const { view, pick } = useReceipt(jobId, decisionId, version);
  const { job, receipt, whatIf, authorisation } = view;
  const nameOf = useNameOf();
  const named = useNamedText();

  if (view.error) return <article className="receipt card notice is-error">{view.error}</article>;
  if (!receipt || !job) {
    return (
      <article className="receipt card receipt-empty">
        <p className="notice">{view.loading ? "Reading the receipt…" : "Pick a job to read its receipt."}</p>
      </article>
    );
  }
  const flagged = receipt.status === "flagged";
  const source = receipt.view === "together" ? "the shared graph" : "its own records";
  return (
    <article className={`receipt card ${view.loading ? "is-loading" : ""}`} aria-live="polite">
      <header className="receipt-head">
        <div>
          <h3>{jobTitle(job.capability, nameOf(job.provider_id))}</h3>
          <p className="receipt-meta">
            Bought by {nameOf(job.buyer_id)}, read from {source}, with {GUARD_WORDS[receipt.guard] ?? receipt.guard}
          </p>
          <blockquote className="receipt-prompt">{job.task_text}</blockquote>
        </div>
        {job.decision_ids.length > 1 && (
          <div className="receipt-decisions" role="group" aria-label="Decisions for this job">
            {job.decision_ids.map((id) => (
              <button key={id} type="button" aria-pressed={id === view.decisionId} onClick={() => pick(id)}>
                {id.replace(`dec-${job.job_id}-`, "Try ")}
              </button>
            ))}
          </div>
        )}
      </header>

      <p className="receipt-verdict">
        <span className={`status-word ${flagged ? "is-orange" : "is-ink"}`}>{flagged ? "Flagged" : "Confident"}</span>{" "}
        <span>
          {receipt.scorer === "udf" ? "Scored inside FalkorDB" : "Scored in Python"} in{" "}
          <span className="tabular">{receipt.graph_ms.toFixed(1)} ms</span>
        </span>
        {receipt.flags.map((flag) => {
          const { providerId, reason } = flagInWords(flag);
          return (
            <span key={flag} className="receipt-flag">
              {nameOf(providerId)} {reason}
            </span>
          );
        })}
      </p>

      <RankingTable ranked={receipt.ranked} chosen={job.provider_id} />
      <Evidence receipt={receipt} />

      {receipt.funding_traces.length > 0 && (
        <div className="receipt-block">
          <h4>Money traced</h4>
          {receipt.funding_traces.map((trace) => (
            <p key={trace.writer_id} className="receipt-path">
              {trace.node_ids.map((id) => (
                <code key={id}>{id}</code>
              ))}
            </p>
          ))}
          {receipt.policies.length > 0 && (
            <p className="label-small">
              Quarantined by <code>{receipt.policies.join(", ")}</code>
            </p>
          )}
        </div>
      )}

      {whatIf && (
        <div className="receipt-block">
          <h4>With the guard {whatIf.guard_tried === "unguarded" ? "off" : whatIf.guard_tried}</h4>
          <p>{named(whatIf.summary)}</p>
        </div>
      )}

      {authorisation && (
        <div className="receipt-block">
          <h4>
            {authorisation.sats} sats, {authorisation.payment_status}
            {job.judge_reason ? `: ${job.judge_reason}` : ""}
          </h4>
          <AuthorityChain authorisation={authorisation} />
        </div>
      )}

      <details className="receipt-queries disclosure">
        <summary>The Cypher behind this decision</summary>
        <ul>
          {receipt.queries.map((query) => (
            <li key={query.name}>
              <code>{query.name}</code>
              <span>{query.purpose}</span>
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
