import type {
  Adversary,
  AgentEval,
  Answer,
  Authorisation,
  GuardMode,
  Health,
  JobStory,
  JobSummary,
  QuarantinePolicy,
  Receipt,
  RoundResult,
  Scoreboard,
  Snapshot,
  Spend,
  TaskStarted,
  View,
  WhatIf,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// Calls one route and returns its JSON, turning the API's detail message into an ApiError
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_BASE + path, {
      ...init,
      headers: { "content-type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, "The API is not reachable.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

// A random id this browser keeps, so the investigator can count its questions
function visitorId(): string {
  try {
    const saved = localStorage.getItem("visitor-id");
    if (saved) return saved;
    const fresh = crypto.randomUUID().slice(0, 18);
    localStorage.setItem("visitor-id", fresh);
    return fresh;
  } catch {
    return "visitor-without-storage";
  }
}

// Sends a JSON body with POST
function post<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
  return call<T>(path, { method: "POST", body: JSON.stringify(body), headers });
}

export const api = {
  health: () => call<Health>("/health"),
  spend: () => call<Spend>("/llm/spend"),
  snapshot: (view: View = "together", buyerId = "observer") =>
    call<Snapshot>(`/graph/snapshot?view=${view}&buyer_id=${buyerId}`),
  startTask: (buyerId: string, text: string, view: View) =>
    post<TaskStarted>("/tasks", { buyer_id: buyerId, text, view }),
  receipt: (decisionId: string) => call<Receipt>(`/decisions/${decisionId}/receipt`),
  whatIf: (decisionId: string, guard: GuardMode = "unguarded") =>
    call<WhatIf>(`/decisions/${decisionId}/what-if?guard=${guard}`),
  whoAuthorised: (paymentId: string) =>
    call<Authorisation>(`/payments/${paymentId}/who-authorised`),
  job: (jobId: string) => call<JobStory>(`/jobs/${jobId}`),
  jobs: (limit = 12) => call<{ jobs: JobSummary[] }>(`/jobs?limit=${limit}`),
  neighbourhood: (nodeId: string, hops = 2) =>
    call<Pick<Snapshot, "nodes" | "edges" | "graph_ms">>(`/nodes/${nodeId}/neighbourhood?hops=${hops}`),
  funding: (nodeId: string) =>
    call<{ chains: string[][]; shared_funders: { funder_id: string; also_funds: string[] }[] }>(
      `/nodes/${nodeId}/funding`,
    ),
  quarantines: () => call<{ policies: QuarantinePolicy[] }>("/quarantines"),
  agentEval: () => call<AgentEval>("/evals/agent"),
  scoreboard: () => call<Scoreboard>("/scoreboard"),
  ask: (question: string) =>
    post<Answer>("/investigator/ask", { question }, { "visitor-id": visitorId() }),
  admin: <T>(route: string, token: string, body: unknown = {}) =>
    post<T>(`/admin/${route}`, body, { "admin-token": token }),
};

// The URL of a server-sent event stream on the API
export function streamUrl(path: string): string {
  return API_BASE + path;
}

// Plays one scoreboard lane live and reports every round until the stream ends
export function playLane(
  lane: string,
  seed: number,
  adversary: Adversary,
  onRound: (round: RoundResult) => void,
): Promise<RoundResult | null> {
  return new Promise((resolve, reject) => {
    const query = `lane=${lane}&seed=${seed}&adversary=${adversary}`;
    const source = new EventSource(streamUrl(`/scoreboard/live?${query}`));
    let last: RoundResult | null = null;
    source.addEventListener("round", (event) => {
      last = JSON.parse((event as MessageEvent).data);
      if (last) onRound(last);
    });
    source.addEventListener("end", () => {
      source.close();
      resolve(last);
    });
    source.onerror = () => {
      source.close();
      if (last) resolve(last);
      else reject(new ApiError(429, "Two lanes are already running. Try again in a few seconds."));
    };
  });
}
