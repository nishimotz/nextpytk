"""nextpytk treeview sample — flat table with selection and double-click."""

from __future__ import annotations

import random
from typing import Any

from nextpytk import Layout, TkApp

COLUMNS = [
    ("name", "名前", 140),
    ("kind", "種類", 80),
    ("score", "スコア", 70, "e"),
]

ROWS: list[tuple[str, str, str]] = [
    ("apple", "果物", "120"),
    ("carrot", "野菜", "80"),
    ("salmon", "魚", "200"),
    ("bread", "穀物", "90"),
]

app = TkApp(title="Treeview table")


def on_open(idx: int) -> dict[str, Any]:
    rows: list[Any] = app.state.get("items_rows", ROWS)
    if idx < 0 or idx >= len(rows):
        return {}
    row = rows[idx]
    return {"status": f"開く: {row[0]}（ダブルクリック）"}


@app.status("status", description="選択行のサマリー")
def status() -> str:
    idx = app.state.get("items", -1)
    rows: list[Any] = app.state.get("items_rows", ROWS)
    if not isinstance(idx, int) or idx < 0 or idx >= len(rows):
        return "行を選択するか、ダブルクリックで開いてください"
    row = rows[idx]
    return f"選択中: {row[0]}（{row[1]} / {row[2]}）"


@app.treeview(
    "items",
    columns=COLUMNS,
    rows_key="items_rows",
    description="サンプル一覧",
    activate=on_open,
)
def on_select(idx: int) -> dict[str, Any]:
    rows: list[Any] = app.state.get("items_rows", ROWS)
    if idx < 0 or idx >= len(rows):
        return {"status": "行を選択してください"}
    row = rows[idx]
    return {"status": f"選択: {row[0]}"}


@app.button("shuffle", label="並べ替え")
def shuffle(_values: dict[str, Any]) -> dict[str, Any]:
    shuffled = list(ROWS)
    random.shuffle(shuffled)
    return {"items_rows": shuffled, "items": -1, "status": "一覧をシャッフルしました"}


layout = (
    Layout()
    .section("status")
    .section("items", fill="both", expand=True)
    .section("shuffle")
)

if __name__ == "__main__":
    app.run(
        layout=layout,
        initial_state={"items_rows": ROWS, "items": -1},
        geometry="420x280",
    )
