"""Streaming responses that close owned synchronous generators on every exit."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any

import anyio
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send


def _next_chunk(content: Iterator[str]) -> str | None:
    try:
        return next(content)
    except StopIteration:
        return None


async def _finish_worker(task: asyncio.Task[Any]) -> asyncio.CancelledError | None:
    """Join a shielded worker even across repeated raw asyncio cancellations."""
    cancellation = None
    with anyio.CancelScope(shield=True):
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
            except Exception:
                # The owner retrieves the worker's outcome after joining it.
                break
    return cancellation


class ClosingStreamingResponse(StreamingResponse):
    def __init__(
        self,
        content: Iterator[str],
        *,
        media_type: str,
        headers: Mapping[str, str],
    ) -> None:
        self._content = content
        self._next_worker: asyncio.Task[str | None] | None = None
        super().__init__(self._iterate(), media_type=media_type, headers=headers)

    async def _iterate(self) -> AsyncIterator[str]:
        while True:
            self._next_worker = asyncio.create_task(run_in_threadpool(_next_chunk, self._content))
            chunk = await asyncio.shield(self._next_worker)
            if chunk is None:
                break
            yield chunk

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        active_error: BaseException | None = None
        try:
            await super().__call__(scope, receive, send)
        except BaseException as error:
            active_error = error
            raise
        finally:
            cancellation = None
            if self._next_worker is not None:
                cancellation = await _finish_worker(self._next_worker)
                if not self._next_worker.cancelled():
                    self._next_worker.exception()
            close = getattr(self._content, "close", None)
            if close is not None:
                close_worker = asyncio.create_task(run_in_threadpool(close))
                close_cancellation = await _finish_worker(close_worker)
                close_worker.result()
                if cancellation is None:
                    cancellation = close_cancellation
            if active_error is None and cancellation is not None:
                raise cancellation
