import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { JobSummary } from "../../api/types";
import { jobTitle, useNameOf } from "../../graph/names";
import { useResource } from "../../hooks/useLive";
import { ReceiptCard } from "./ReceiptCard";
import "./receipts.css";

interface Props {
  version: number;
  openDecision: string | null;
  onOpen: (decisionId: string | null) => void;
}

// The tone a payment status is written in
function paymentTone(status: string | null): string {
  if (status === "refunded") return "is-orange";
  if (status === "held") return "is-blue";
  return status ? "is-ink" : "is-slate";
}

// Every payment has a receipt: a list of the agent's jobs and the receipt of the one picked
export function ReceiptSection({ version, openDecision, onOpen }: Props) {
  const jobs = useResource(() => api.jobs(12), [version]);
  const nameOf = useNameOf();
  const [jobId, setJobId] = useState<string | null>(null);
  const list: JobSummary[] = jobs.data?.jobs ?? [];
  const activeJob = jobId ?? list[0]?.job_id ?? null;

  useEffect(() => {
    if (openDecision) setJobId(null);
  }, [openDecision]);

  return (
    <section className="band band-mist" id="receipts" aria-labelledby="receipts-title">
      <div className="band-head">
        <div>
          <h2 id="receipts-title">Every payment has a receipt.</h2>
          <p className="band-lede">
            Each decision is a node in the graph, linked to the evidence it counted, the claims it ignored, the money it
            traced and the payment it authorised. Replay it with the guard off to see what the guard changed.
          </p>
        </div>
      </div>
      <div className="receipts">
        <nav className="receipt-list card" aria-label="Recent jobs">
          <p className="label-small">Recent jobs</p>
          {jobs.loading && list.length === 0 && <p className="notice">Reading jobs from FalkorDB…</p>}
          {jobs.error && <p className="notice is-error">{jobs.error.message}</p>}
          {!jobs.loading && list.length === 0 && !jobs.error && (
            <p className="notice">No agent jobs yet. Run a task above and its receipt lands here.</p>
          )}
          <ul>
            {list.map((job) => (
              <li key={job.job_id}>
                <button
                  type="button"
                  aria-pressed={!openDecision && job.job_id === activeJob}
                  onClick={() => {
                    onOpen(null);
                    setJobId(job.job_id);
                  }}
                >
                  <span className="receipt-list-title">
                    {jobTitle(job.capability, nameOf(job.provider_id))}
                  </span>
                  <span className="receipt-list-meta">
                    {nameOf(job.buyer_id)} ·{" "}
                    <span className={`status-word ${paymentTone(job.payment_status)}`}>
                      {job.payment_status ?? "unpaid"}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <ReceiptCard jobId={openDecision ? null : activeJob} decisionId={openDecision} version={version} />
      </div>
    </section>
  );
}
