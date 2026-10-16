import { useEffect, useRef } from "react";
import type { RunState, ToolStep } from "../../agent/steps";
import { algorithmsOf, graphMs, summarise, TOOL_TITLES } from "../../agent/summaries";

interface Props {
  run: RunState;
  selected?: ToolStep;
  onSelect: (step: ToolStep | undefined) => void;
}

// What to show before the first tool call
function EmptyTrace({ run }: { run: RunState }) {
  if (run.status === "starting") return <p className="trace-empty">Planning the jobs…</p>;
  if (run.status === "failed") return <p className="trace-empty is-orange">{run.error}</p>;
  return (
    <p className="trace-empty">
      Every tool the agent calls appears here as it happens, with what it found and how long FalkorDB took. Click a
      step to see what it touched in the graph.
    </p>
  );
}

// The agent's tool calls in order, one row per call, grouped by job
export function ToolTrace({ run, selected, onSelect }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const stepCount = run.jobs.reduce((total, job) => total + job.steps.length, 0);

  useEffect(() => {
    const box = boxRef.current;
    if (box && stepCount > 0 && !selected) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
  }, [stepCount, selected]);

  return (
    <div className="trace" aria-live="polite" ref={boxRef}>
      <div className="trace-head">
        <span className="label-small">Tool calls</span>
        {selected && (
          <button type="button" className="text-link trace-follow" onClick={() => onSelect(undefined)}>
            Follow the latest
          </button>
        )}
      </div>
      {stepCount === 0 ? (
        <EmptyTrace run={run} />
      ) : (
        run.jobs.map((job) => (
          <div key={job.job.job_id} className="trace-job">
            <p className="trace-job-title">
              {job.job.capability.replace("_", " ")} <code>{job.job.job_id}</code>
            </p>
            <ol>
              {job.steps.map((step) => {
                const ms = graphMs(step);
                const algorithms = algorithmsOf(step);
                const isSelected = selected?.jobId === step.jobId && selected.index === step.index;
                const tone = step.ok === false ? "is-refused" : step.name === "quarantine" ? "is-alert" : "";
                return (
                  <li key={step.index}>
                    <button
                      type="button"
                      className={`trace-step ${tone}`}
                      aria-pressed={isSelected}
                      onClick={() => onSelect(isSelected ? undefined : step)}
                    >
                      <span className="trace-step-name">
                        {TOOL_TITLES[step.name] ?? step.name}
                        {ms !== null && <span className="trace-ms tabular">{ms.toFixed(1)} ms</span>}
                      </span>
                      <span className="trace-step-summary">{summarise(step)}</span>
                      {algorithms.length > 0 && (
                        <span className="trace-algorithms">
                          {algorithms.map((name) => (
                            <code key={name}>{name}</code>
                          ))}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
        ))
      )}
      {run.status === "running" && <p className="trace-working">Working</p>}
    </div>
  );
}
