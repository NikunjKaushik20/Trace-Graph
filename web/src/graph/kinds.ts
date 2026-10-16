import type { GraphNode } from "../api/types";

export type NodeKind =
  | "principal"
  | "buyer"
  | "provider"
  | "writer"
  | "root"
  | "wallet"
  | "task"
  | "job"
  | "payment"
  | "decision"
  | "claim"
  | "ring"
  | "policy"
  | "lesson";

interface KindStyle {
  radius: number;
  label: boolean;
  hollow: boolean;
}

export const KIND_STYLE: Record<NodeKind, KindStyle> = {
  principal: { radius: 7, label: true, hollow: false },
  buyer: { radius: 7, label: true, hollow: false },
  provider: { radius: 6, label: true, hollow: false },
  writer: { radius: 3.2, label: false, hollow: false },
  root: { radius: 5.5, label: false, hollow: true },
  wallet: { radius: 4, label: false, hollow: true },
  task: { radius: 4.5, label: false, hollow: false },
  job: { radius: 2, label: false, hollow: false },
  payment: { radius: 1.8, label: false, hollow: false },
  decision: { radius: 4.5, label: false, hollow: false },
  claim: { radius: 2.4, label: false, hollow: true },
  ring: { radius: 7, label: false, hollow: true },
  policy: { radius: 5, label: false, hollow: false },
  lesson: { radius: 4, label: false, hollow: false },
};

const LABEL_ORDER: [string, NodeKind][] = [
  ["Principal", "principal"],
  ["Buyer", "buyer"],
  ["Provider", "provider"],
  ["Ring", "ring"],
  ["Policy", "policy"],
  ["Decision", "decision"],
  ["Root", "root"],
  ["Wallet", "wallet"],
  ["Claim", "claim"],
  ["Task", "task"],
  ["Job", "job"],
  ["Payment", "payment"],
  ["Lesson", "lesson"],
  ["Writer", "writer"],
];

// The one kind a node is drawn as, picked by its most specific label
export function kindOf(node: GraphNode): NodeKind {
  const match = LABEL_ORDER.find(([label]) => node.labels.includes(label));
  return match ? match[1] : "job";
}

// A short, readable name for a node: its own name, or its id without the prefix noise
export function displayName(node: GraphNode): string {
  if (node.name) return node.name;
  return node.id.replace(/^claim:/, "claim ").split(":")[0];
}

export const KIND_NAMES: Record<NodeKind, string> = {
  principal: "Principal",
  buyer: "Buyer agent",
  provider: "Provider",
  writer: "Review writer",
  root: "Funding root",
  wallet: "Wallet",
  task: "Task",
  job: "Job",
  payment: "Payment",
  decision: "Decision",
  claim: "Ignored claim",
  ring: "Ring",
  policy: "Quarantine",
  lesson: "Lesson",
};
