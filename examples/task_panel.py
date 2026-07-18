"""nextpytk demo: labels, entries, buttons updating a **shared state dict**.

Shows the decorator API + section-based layout.
"""

from nextpytk import TkApp, Layout
from nextpytk.types import Fill

app = TkApp(title="nextpytk task panel")


# --- Status row ---

@app.status("msg", description="Operation feedback")
def msg():
    return "Ready"


@app.status("phase", description="Current phase")
def phase():
    return "Idle"


@app.status("count", description="Processed count")
def count():
    return "0 items"


# --- Inputs ---

@app.entry("name", placeholder="Task name (required)")
def on_name_change(value):
    return {"msg": f"Task name: {value}"}


@app.entry("max_sec", placeholder="Max seconds (e.g. 5)")
def on_sec_change(value):
    return {"msg": f"Timeout: {value} sec"}


# --- Actions ---

PHASE = {"idle": "Idle", "running": "Running", "done": "Done", "paused": "Paused"}


@app.button("start", label="▶ Start")
def on_start(values):
    name = values.get("name", "").strip()
    if not name:
        return {"msg": "Please enter a task name"}
    return {"msg": f"Starting \"{name}\"", "phase": PHASE["running"]}


@app.button("pause", label="⏸ Pause")
def on_pause(values):
    return {"msg": "Paused", "phase": PHASE["paused"]}


@app.button("reset", label="⏹ Reset")
def on_reset(values):
    return {"msg": "Reset", "phase": PHASE["idle"], "count": "0 items"}


@app.button("countup", label="+1")
def on_countup(values):
    c = app.state.get("count", "0 items")
    n = 1
    if c.endswith(" items"):
        try:
            n = int(c.split()[0]) + 1
        except ValueError:
            pass
    return {"count": f"{n} items", "msg": f"Count: {n}"}


# --- Layout ---

layout = (
    Layout()
    .section("msg")
    .section("phase", "count")
    .section("name", fill=Fill.X)
    .section("max_sec", fill=Fill.X)
    .section("start", "pause")
    .section("reset", "countup")
)

if __name__ == "__main__":
    app.run(layout=layout)
