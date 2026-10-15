import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Health, Snapshot, Spend, View } from "../api/types";

// Polls /health and the spend meter, so the page always says whether FalkorDB is there
export function useHealth(everyMs = 8000) {
  const [health, setHealth] = useState<Health | null>(null);
  const [spend, setSpend] = useState<Spend | null>(null);
  const [reachable, setReachable] = useState(true);

  // Reads both once; a 503 still carries the health body, so it is read either way
  const refresh = useCallback(async () => {
    try {
      const response = await fetch((import.meta.env.VITE_API_BASE ?? "") + "/health");
      setHealth(await response.json());
      setReachable(true);
    } catch {
      setReachable(false);
      setHealth(null);
    }
    api.spend().then(setSpend, () => undefined);
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, everyMs);
    return () => window.clearInterval(timer);
  }, [refresh, everyMs]);

  return { health, spend, reachable, refresh };
}

// Loads a graph snapshot while enabled and reloads it on demand, at most once every 600 ms
export function useSnapshot(view: View = "together", buyerId = "observer", enabled = true) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<number | null>(null);

  // Fetches the snapshot now
  const load = useCallback(async () => {
    try {
      setSnapshot(await api.snapshot(view, buyerId));
      setError(null);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "The graph could not be read.");
    }
  }, [view, buyerId]);

  // Asks for a reload soon, folding bursts of requests into one
  const reload = useCallback(() => {
    if (pending.current !== null) return;
    pending.current = window.setTimeout(() => {
      pending.current = null;
      load();
    }, 600);
  }, [load]);

  useEffect(() => {
    if (enabled) load();
  }, [load, enabled]);

  return { snapshot, error, reload, load };
}

// Loads one API resource once, with its loading and error state
export function useResource<T>(read: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // Runs the read and records how it went
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await read());
      setError(null);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure : new ApiError(0, "The API did not answer. Check your connection and reload the page."));
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, error, loading, load };
}
