import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, streamUrl } from "../api/client";
import type { AgentEvent, View } from "../api/types";
import { applyEvent, IDLE_RUN, type RunState } from "./steps";

const EVENT_KINDS = ["plan", "tool_call", "tool_result", "narration", "error"] as const;

// Starts agent tasks and follows their event stream; onGraphChange fires after each tool result
export function useAgentRun(onGraphChange: () => void) {
  const [run, setRun] = useState<RunState>(IDLE_RUN);
  const sourceRef = useRef<EventSource | null>(null);
  const graphChanged = useRef(onGraphChange);
  graphChanged.current = onGraphChange;

  useEffect(() => () => sourceRef.current?.close(), []);

  // Opens the task's event stream and folds every event into the run
  const follow = useCallback((eventsUrl: string) => {
    const source = new EventSource(streamUrl(eventsUrl));
    sourceRef.current = source;
    for (const kind of EVENT_KINDS) {
      source.addEventListener(kind, (message) => {
        const event = JSON.parse((message as MessageEvent).data) as AgentEvent;
        setRun((state) => applyEvent(state, event));
        if (kind === "tool_result") graphChanged.current();
      });
    }
    source.addEventListener("end", (message) => {
      const ending = JSON.parse((message as MessageEvent).data) as { status: string; error: string | null };
      source.close();
      setRun((state) => ({
        ...state,
        status: ending.status === "done" ? "done" : "failed",
        error: ending.error ?? undefined,
      }));
      graphChanged.current();
    });
    source.onerror = () => {
      source.close();
      setRun((state) =>
        state.status === "running" || state.status === "starting"
          ? { ...state, status: "failed", error: "The event stream closed before the task finished." }
          : state,
      );
    };
  }, []);

  // Sends a task to one buyer agent and starts following it
  const start = useCallback(
    async (buyerId: string, text: string, view: View) => {
      sourceRef.current?.close();
      setRun({ ...IDLE_RUN, buyerId, status: "starting" });
      try {
        const started = await api.startTask(buyerId, text, view);
        setRun((state) => ({ ...state, taskId: started.task_id }));
        follow(started.events_url);
      } catch (error) {
        const message = error instanceof ApiError ? error.message : "The task could not start.";
        setRun((state) => ({ ...state, status: "failed", error: message }));
      }
    },
    [follow],
  );

  return { run, start };
}
