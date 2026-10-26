"""Adversarial cancellation while a synchronous generator is executing."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator
from contextlib import suppress
from types import GeneratorType
from typing import Any

import pytest

from app.api.streaming import ClosingStreamingResponse


async def wait_until(predicate: Any) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.001)

    await asyncio.wait_for(poll(), timeout=2)


@pytest.mark.parametrize("cancel_twice", [False, True])
@pytest.mark.parametrize("worker_fails", [False, True])
def test_cancel_during_next_waits_for_worker_then_closes_and_preserves_cancel(
    cancel_twice: bool,
    worker_fails: bool,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()
    closes: list[bool] = []

    def chunks() -> Generator[str, None, None]:
        try:
            yield "header"
            entered.set()
            if not release.wait(timeout=3):
                raise TimeoutError("Test did not release worker")
            if worker_fails:
                raise RuntimeError("Synthetic read failure after cancellation")
            yield "data"
        finally:
            closes.append(True)
            closed.set()

    async def run() -> None:
        generator = chunks()
        assert isinstance(generator, GeneratorType)
        response = ClosingStreamingResponse(generator, media_type="text/csv", headers={})

        async def receive() -> Any:
            await asyncio.Event().wait()

        async def send(message: Any) -> None:
            pass

        scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
        task = asyncio.create_task(response(scope, receive, send))
        error: BaseException | None = None
        try:
            await wait_until(entered.is_set)
            task.cancel("original download cancellation")
            await asyncio.sleep(0.02)
            if cancel_twice:
                task.cancel("repeated cleanup cancellation")
                await asyncio.sleep(0.02)
            exited_early = task.done()
            closed_early = closed.is_set()
            release.set()
            try:
                await asyncio.wait_for(task, timeout=2)
            except BaseException as caught:
                error = caught
            assert not exited_early, f"Response exited with worker active: {error!r}"
            assert not closed_early
            assert closed.is_set()
            assert closes == [True]
            assert isinstance(error, asyncio.CancelledError), repr(error)
            assert error.args == ("original download cancellation",)
        finally:
            release.set()
            if not task.done():
                with suppress(BaseException):
                    await asyncio.wait_for(task, timeout=2)
            # Recovery only for a failing implementation, after recording the assertions.
            await wait_until(lambda: not generator.gi_running)
            generator.close()

    asyncio.run(run())


def test_cancel_during_close_joins_worker_and_then_propagates_cancel() -> None:
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()
    closes: list[bool] = []

    class Chunks:
        def __iter__(self) -> Chunks:
            return self

        def __next__(self) -> str:
            raise StopIteration

        def close(self) -> None:
            closes.append(True)
            entered.set()
            if not release.wait(timeout=3):
                raise TimeoutError("Test did not release close worker")
            closed.set()

    async def run() -> None:
        response = ClosingStreamingResponse(Chunks(), media_type="text/csv", headers={})

        async def receive() -> Any:
            await asyncio.Event().wait()

        async def send(message: Any) -> None:
            pass

        task = asyncio.create_task(
            response(
                {"type": "http", "asgi": {"spec_version": "2.4"}},
                receive,
                send,
            )
        )
        try:
            await wait_until(entered.is_set)
            task.cancel("cancel while closing")
            await asyncio.sleep(0.02)
            task.cancel("repeated cancel while closing")
            await asyncio.sleep(0.02)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError, match="^cancel while closing$"):
                await asyncio.wait_for(task, timeout=2)
            assert closed.is_set()
            assert closes == [True]
        finally:
            release.set()
            if not task.done():
                with suppress(BaseException):
                    await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
