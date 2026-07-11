"""nextpytk progressbar sample — determinate updates via ``app.run_async`` + ``spawn``."""

from __future__ import annotations

import asyncio
from typing import Any

from nextpytk import Layout, TkApp

app = TkApp(title="Progressbar demo")

app.progressbar("progress", maximum=100, length=360, description="0–100% の進捗")


@app.status("status")
def status() -> str:
    return str(app.state.get("status", "「開始」を押してください"))


@app.button("start", label="開始")
def start(_values: dict[str, Any]) -> dict[str, Any]:
    app.spawn(_run_job())
    return {"status": "処理中…", "progress": 0, "progress_running": False}


@app.button("pulse", label="不定（くるくる）")
def pulse(_values: dict[str, Any]) -> dict[str, Any]:
    running = not bool(app.state.get("progress_running", False))
    return {
        "progress_running": running,
        "status": "不定モード ON" if running else "不定モード OFF",
    }


@app.button("reset", label="リセット")
def reset(_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "リセットしました",
        "progress": 0,
        "progress_running": False,
    }


async def _run_job() -> None:
    for i in range(0, 101, 5):
        await asyncio.sleep(0.07)
        app.apply_state({"progress": i, "status": f"{i}%"})
    app.apply_state({"progress": 100, "status": "完了", "progress_running": False})


layout = (
    Layout()
    .section("status")
    .section("progress", fill="x")
    .section("start", "pulse", "reset")
)

if __name__ == "__main__":
    app.run_async(
        layout=layout,
        initial_state={"progress": 0, "progress_running": False},
        geometry="440x160",
    )
