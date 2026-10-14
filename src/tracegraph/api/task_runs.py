import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal

from tracegraph.agent.runs import AgentEvent, TaskRun

TaskStatus = Literal["running", "done", "failed"]
logger = logging.getLogger(__name__)


@dataclass
class TaskHandle:
    task_id: str
    buyer_id: str
    text: str
    events: list[AgentEvent] = field(default_factory=list)
    status: TaskStatus = "running"
    run: TaskRun | None = None
    error: str | None = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    # Adds an event and wakes everyone following this task
    async def publish(self, event: AgentEvent) -> None:
        async with self.changed:
            self.events.append(event)
            self.changed.notify_all()

    # Marks the task finished, with its run or the error that stopped it
    async def finish(self, run: TaskRun | None, error: str | None = None) -> None:
        async with self.changed:
            self.run, self.error = run, error
            self.status = "failed" if error else "done"
            self.changed.notify_all()

    # Every event so far, then each new one as it happens, until the task ends
    async def follow(self) -> AsyncIterator[tuple[int, AgentEvent]]:
        seen = 0
        while True:
            fresh, ended = await self.events_after(seen)
            for event in fresh:
                yield seen, event
                seen += 1
            if ended:
                return

    # Waits until there are events past the first `seen`, or the task has ended
    async def events_after(self, seen: int) -> tuple[list[AgentEvent], bool]:
        async with self.changed:
            await self.changed.wait_for(lambda: len(self.events) > seen or self.status != "running")
            fresh = self.events[seen:]
            return fresh, self.status != "running" and not fresh


class TaskRegistry:
    # Tasks started over HTTP, kept in memory while the server runs
    def __init__(self) -> None:
        self.handles: dict[str, TaskHandle] = {}
        self.running: set[asyncio.Task[None]] = set()

    # Starts a task in the background and returns its handle at once
    def start(
        self,
        handle: TaskHandle,
        work: Callable[[TaskHandle], Coroutine[Any, Any, TaskRun]],
    ) -> TaskHandle:
        self.handles[handle.task_id] = handle
        background = asyncio.create_task(self.run_to_end(handle, work))
        self.running.add(background)
        background.add_done_callback(self.running.discard)
        return handle

    # Runs the work and records how it ended, whatever happens
    async def run_to_end(
        self, handle: TaskHandle, work: Callable[[TaskHandle], Coroutine[Any, Any, TaskRun]]
    ) -> None:
        try:
            await handle.finish(await work(handle))
        except Exception as error:
            logger.exception("task %s failed", handle.task_id)
            await handle.finish(None, f"{type(error).__name__}: {error}")

    # The handle for a task id, if this server started it
    def get(self, task_id: str) -> TaskHandle | None:
        return self.handles.get(task_id)
