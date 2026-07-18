"""nextpytk progressbar sample — determinate updates via ``app.run_async`` + ``spawn``."""

from __future__ import annotations

import asyncio
from typing import Any

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

app = TkApp(title="Progressbar demo")

app.progressbar("progress", maximum=100, length=360, description="0–100% progress")


@app.status("status")
def status() -> str:
    return str(app.state.get("status", "Press Start"))


@app.button("start", label="Start")
def start(_values: dict[str, Any]) -> dict[str, Any]:
    app.spawn(_run_job())
    return {"status": "Processing…", "progress": 0, "progress_running": False}


@app.button("pulse", label="Indeterminate")
def pulse(_values: dict[str, Any]) -> dict[str, Any]:
    running = not bool(app.state.get("progress_running", False))
    return {
        "progress_running": running,
        "status": "Indeterminate mode ON" if running else "Indeterminate mode OFF",
    }


@app.button("reset", label="Reset")
def reset(_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "Reset",
        "progress": 0,
        "progress_running": False,
    }


async def _run_job() -> None:
    for i in range(0, 101, 5):
        await asyncio.sleep(0.07)
        app.apply_state({"progress": i, "status": f"{i}%"})
    app.apply_state({"progress": 100, "status": "Done", "progress_running": False})


layout = (
    Layout()
    .section("status")
    .section("progress", fill=Fill.X)
    .section("start", "pulse", "reset", fill=Fill.X, expand=True)
)

if __name__ == "__main__":
    app.run_async(
        layout=layout,
        initial_state={"progress": 0, "progress_running": False},
        geometry="560x160",
    )
