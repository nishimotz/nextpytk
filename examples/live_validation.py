"""nextpytk live validation — Tcl-var trace ingest demo.

This example requires ``ingest_trace=True`` (v0.4.8).

The search entry has **no** on-change logic: its callback returns an empty
dict. Every keystroke is ingested from the Tcl variable into ``state["query"]``
via a ``trace_add("write")`` and batched into one sync pass. Because
``apply_state`` is what drives ``enabled_if``, derived labels, and menubar
state, those now react to typing in real time without writing a single
state-returning callback.
"""

from __future__ import annotations

from nextpytk import TkApp, Layout
from nextpytk.types import Fill

app = TkApp(title="Live validation (trace ingest)", ingest_trace=True)

ITEMS = [
    "Python", "PyPy", "PySide", "tkinter", "Tcl/Tk", "Flutter",
    "Dart", "React", "Redux", "TypeScript", "Kotlin", "Swift",
]


# The entry has no on-change logic: the trace does the work.
@app.entry("query", placeholder="Type to filter the list")
def on_query() -> dict:
    return {}


@app.label("count", description="live match count")
def count() -> str:
    q = (app.state.get("query") or "").lower()
    matches = [n for n in ITEMS if q in n.lower()]
    return f"{len(matches)} / {len(ITEMS)} items match"


@app.status("state_note", description="ingest feedback")
def state_note() -> str:
    # Updated per keystroke because the trace writes state["query"].
    q = app.state.get("query") or ""
    return f"state['query'] = {q!r}"


@app.listbox("items", items=ITEMS, height=10)
def on_items(_index: int) -> dict:
    return {}


# Enabled only while there is non-whitespace input — reacts per keystroke.
@app.button("go", label="Go", enabled_if=lambda v: bool((v.get("query") or "").strip()))
def go(values: dict) -> dict:
    return {"state_note": f"Go pressed with {values.get('query')!r}"}


if __name__ == "__main__":
    app.run(
        layout=(
            Layout()
            .section("query")
            .section("count")
            .section("items", fill=Fill.BOTH, expand=True)
            .section("go")
            .status("state_note")
        ),
        geometry="520x400",
    )
