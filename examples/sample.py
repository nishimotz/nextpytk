"""Decorator API sample: widgets as functions, layout declared separately.

Usage::

    uv run python examples/sample.py
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Decorator sample")


@app.status("status", description="Shows the current state")
def status():
    return "Idle"


@app.button("submit", label="Send", enabled_if=lambda v: bool((v.get("input") or "").strip()))
def on_submit(values):
    return {"status": f"Sent: {values.get('input', '')}"}


@app.button("clear", label="Clear")
def on_clear(values):
    return {"status": "Idle", "input": ""}


@app.entry("input", placeholder="Type here")
def on_change(value):
    if not value:
        return {"status": "Idle"}
    return {"status": f"Typing: {value}"}


layout = (
    Layout()
    .section("status")
    .section("input")
    .section("submit", "clear")
)

if __name__ == "__main__":
    app.run(layout=layout)
