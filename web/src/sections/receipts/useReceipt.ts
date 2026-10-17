import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Authorisation, JobStory, Receipt, WhatIf } from "../../api/types";

export interface ReceiptView {
  job: JobStory | null;
  decisionId: string | null;
  receipt: Receipt | null;
  whatIf: WhatIf | null;
  authorisation: Authorisation | null;
  loading: boolean;
  error: string | null;
}

const EMPTY: ReceiptView = {
  job: null,
  decisionId: null,
  receipt: null,
  whatIf: null,
  authorisation: null,
  loading: false,
  error: null,
};

// Loads a job, one of its decisions, that decision's receipt and what-if, and who paid
export function useReceipt(jobId: string | null, decisionId: string | null, version: number) {
  const [view, setView] = useState<ReceiptView>(EMPTY);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => setPicked(decisionId), [decisionId, jobId]);

  useEffect(() => {
    if (!jobId && !picked) {
      setView(EMPTY);
      return;
    }
    let current = true;
    setView((before) => ({ ...before, loading: true, error: null }));
    load(jobId, picked)
      .then((loaded) => current && setView({ ...loaded, loading: false, error: null }))
      .catch((failure) => {
        const message = failure instanceof ApiError ? failure.message : "The receipt could not be read.";
        if (current) setView({ ...EMPTY, error: message });
      });
    return () => {
      current = false;
    };
  }, [jobId, picked, version]);

  return { view, pick: setPicked };
}

// Fetches everything the receipt card shows, starting from a job or a decision
async function load(jobId: string | null, decisionId: string | null): Promise<Omit<ReceiptView, "loading" | "error">> {
  let receipt = decisionId ? await api.receipt(decisionId) : null;
  const job = await api.job(receipt?.job_id ?? jobId ?? "");
  const chosen = decisionId ?? job.decision_ids[job.decision_ids.length - 1] ?? null;
  if (!receipt && chosen) receipt = await api.receipt(chosen);
  const [whatIf, authorisation] = await Promise.all([
    chosen ? api.whatIf(chosen).catch(() => null) : null,
    job.payment_id ? api.whoAuthorised(job.payment_id).catch(() => null) : null,
  ]);
  return { job, decisionId: chosen, receipt, whatIf, authorisation };
}
