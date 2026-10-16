import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { Snapshot } from "../api/types";

type NameOf = (id: string | null | undefined) => string;

const NamesContext = createContext<NameOf>((id) => id ?? "");

// Gives every section the names the graph holds for buyers, providers and principals
export function NamesProvider({ snapshot, children }: { snapshot: Snapshot | null; children: ReactNode }) {
  const nameOf = useMemo<NameOf>(() => {
    const names = new Map(snapshot?.nodes.filter((node) => node.name).map((node) => [node.id, String(node.name)]));
    return (id) => (id ? (names.get(id) ?? id) : "");
  }, [snapshot]);
  return <NamesContext.Provider value={nameOf}>{children}</NamesContext.Provider>;
}

// The readable name for a node id, or the id itself when the graph has no name for it
export function useNameOf(): NameOf {
  return useContext(NamesContext);
}

const NAMED_ID = /\b(?:prov|buyer|principal)-[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]/g;

// Swaps provider and buyer ids inside a sentence for their names
export function useNamedText(): (text: string) => string {
  const nameOf = useNameOf();
  return (text) => text.replace(NAMED_ID, (id) => nameOf(id));
}

// A job's title in sentence case: what was bought and who did it
export function jobTitle(capability: string, provider: string): string {
  const job = capability.replaceAll("_", " ");
  const head = job.charAt(0).toUpperCase() + job.slice(1);
  return provider ? `${head} by ${provider}` : `${head}, nobody hired`;
}

export const GUARD_WORDS: Record<string, string> = {
  closed: "fleet-only reviews",
  open: "funding check",
  unguarded: "no guard",
};
