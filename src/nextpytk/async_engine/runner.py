"""Asyncio scheduler and cooperative mainloop integration for Tkinter."""

from __future__ import annotations

import asyncio
import tkinter as tk
from collections.abc import Awaitable, Callable
from typing import Any

# Async job type alias
AsyncJob = Callable[..., Awaitable[dict[str, Any] | None]]


class AsyncEngine:
    """Manages background asyncio tasks, named jobs, and cooperative event loop integration."""

    def __init__(self) -> None:
        self.jobs: dict[str, AsyncJob] = {}
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.event_loop: asyncio.AbstractEventLoop | None = None
        self.async_stop: bool = False

    def register_job(self, name: str, fn: AsyncJob) -> AsyncJob:
        """Register a coroutine function as a named job."""
        self.jobs[name] = fn
        return fn

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        """Schedule an async task on the running event loop.

        Raises RuntimeError if no event loop is running.
        """
        if self.event_loop is None or not self.event_loop.is_running():
            raise RuntimeError("No running event loop -- call app.run() first")
        task = asyncio.ensure_future(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    def stop(self) -> None:
        """Signal the async mainloop to stop gracefully."""
        self.async_stop = True

    async def async_poll(self, root: tk.Misc | None) -> None:
        """Poll Tk events cooperatively with asyncio."""
        if root is None:
            return
        try:
            while root.tk.dooneevent(0):
                pass
        except tk.TclError:
            return

    async def async_mainloop(self, root: tk.Tk | None, *, sleep_interval: float = 0.01) -> None:
        """Cooperative async mainloop: Tk event processing + asyncio scheduler.

        Terminates when the window is closed (via WM_DELETE_WINDOW)
        or stop() is called.
        """
        if root is None:
            return

        self.async_stop = False

        def _on_close() -> None:
            self.async_stop = True
            try:
                root.destroy()
            except tk.TclError:
                pass

        root.protocol("WM_DELETE_WINDOW", _on_close)

        try:
            while not self.async_stop:
                try:
                    root.update()
                except tk.TclError:
                    break
                await asyncio.sleep(sleep_interval)
        finally:
            self.async_stop = True
