from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.runtime.schemas import StreamEvent

_END = object()


class MemoryStreamBridge:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._queues: dict[int, asyncio.Queue[StreamEvent | object]] = {}
        self._event_counters: dict[int, int] = {}

    async def ensure_run(self, run_id: int) -> None:
        async with self._lock:
            self._queues.setdefault(run_id, asyncio.Queue())
            self._event_counters.setdefault(run_id, 0)

    async def publish(self, run_id: int, event: str, data: Any) -> None:
        queue = await self._get_queue(run_id)
        event_id = self._event_counters.get(run_id, 0) + 1
        self._event_counters[run_id] = event_id
        await queue.put(StreamEvent(id=event_id, event=event, data=data))

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, run_id: int, event: str, data: Any) -> None:
        future = asyncio.run_coroutine_threadsafe(self.publish(run_id, event, data), loop)
        future.result()

    async def publish_end(self, run_id: int) -> None:
        queue = await self._get_queue(run_id)
        await queue.put(_END)

    def publish_end_threadsafe(self, loop: asyncio.AbstractEventLoop, run_id: int) -> None:
        future = asyncio.run_coroutine_threadsafe(self.publish_end(run_id), loop)
        future.result()

    async def subscribe(self, run_id: int, *, heartbeat_interval: float = 15.0) -> AsyncIterator[StreamEvent]:
        queue = await self._get_queue(run_id)
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except TimeoutError:
                yield StreamEvent(id=0, event="heartbeat", data={})
                continue

            if item is _END:
                yield StreamEvent(id=0, event="end", data={})
                return
            yield item  # type: ignore[misc]

    async def cleanup(self, run_id: int, *, delay: float = 300) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        async with self._lock:
            self._queues.pop(run_id, None)
            self._event_counters.pop(run_id, None)

    async def _get_queue(self, run_id: int) -> asyncio.Queue[StreamEvent | object]:
        async with self._lock:
            queue = self._queues.setdefault(run_id, asyncio.Queue())
            self._event_counters.setdefault(run_id, 0)
            return queue


_stream_bridge = MemoryStreamBridge()


def get_stream_bridge() -> MemoryStreamBridge:
    return _stream_bridge
