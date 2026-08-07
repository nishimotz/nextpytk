"""nextpytk treeview sample — flat table with selection and double-click."""

from __future__ import annotations

import random
from typing import Any

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

COLUMNS = [
    ("name", "Name", 140),
    ("kind", "Kind", 80),
    ("score", "Score", 70, "e"),
]

ROWS: list[tuple[str, str, str]] = [
    ("apple", "Fruit", "120"),
    ("carrot", "Vegetable", "80"),
    ("salmon", "Fish", "200"),
    ("bread", "Grain", "90"),
]

app = TkApp(title="Treeview table")


def on_open(idx: int, row: list[Any]) -> dict[str, Any]:
    if idx < 0:
        return {}
    return {"status": f"Open: {row[0]} (double-click)"}


@app.status("status", description="Selected row summary")
def status() -> str:
    idx = app.state.get("items", -1)
    rows: list[Any] = app.state.get("items_rows", ROWS)
    if not isinstance(idx, int) or idx < 0 or idx >= len(rows):
        return "Select a row or double-click to open"
    row = rows[idx]
    return f"Selected: {row[0]} ({row[1]} / {row[2]})"


@app.treeview(
    "items",
    columns=COLUMNS,
    rows_key="items_rows",
    description="Sample list",
    activate=on_open,
)
def on_select(idx: int) -> dict[str, Any]:
    rows: list[Any] = app.state.get("items_rows", ROWS)
    if idx < 0 or idx >= len(rows):
        return {"status": "Please select a row"}
    row = rows[idx]
    return {"status": f"Selected: {row[0]}"}


@app.button("shuffle", label="Shuffle")
def shuffle(_values: dict[str, Any]) -> dict[str, Any]:
    shuffled = list(ROWS)
    random.shuffle(shuffled)
    return {"items_rows": shuffled, "items": -1, "status": "List shuffled"}


layout = (
    Layout()
    .section("shuffle", side="bottom")
    .section("status")
    .section("items", fill=Fill.BOTH, expand=True)
)

if __name__ == "__main__":
    app.run(
        layout=layout,
        initial_state={"items_rows": ROWS, "items": -1},
        geometry="420x280",
    )
