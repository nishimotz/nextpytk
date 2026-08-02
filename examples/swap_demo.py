"""Dynamic layout switching demo — swap the main area, keep the toolbar.

Mirrors HTMX ``hx-target`` / ``hx-swap``: ``Layout.target()`` reserves a swap
region, and ``@app.swap`` declares the variants that fill it. The toolbar and
status sections stay fixed while only the target region's contents change.
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

app = TkApp(title="Swap area demo")


@app.status("info")
def info() -> str:
    return "Toggle the main area: folder tree <-> paired diff"


@app.button("go_dir", label="Folder view")
def go_dir(_v):
    app.swap_view("main_area", "dir")
    return {"info": "Folder view"}


@app.button("go_file", label="File view")
def go_file(_v):
    app.swap_view("main_area", "file")
    return {"info": "File view"}


@app.label("dir_heading")
def dir_heading() -> str:
    return "Folder compare — nextpytk/ vs sample-lib/"


@app.treeview(
    "dir_tree",
    columns=[
        ("relpath", "Path", 200, "w"),
        ("status", "Status", 70, "center"),
        ("left_size", "Left", 80, "e"),
        ("right_size", "Right", 80, "e"),
    ],
    height=12,
    rows_key="dir_rows",
    widget_kwargs={"padding": 8},
)
def dir_tree(idx):
    return {}


@app.text("left_text", readonly=True)
def left_text(value):
    return {}


@app.text("right_text", readonly=True)
def right_text(value):
    return {}


layout = (
    Layout()
    .cluster("go_dir", "go_file", "info")
    .target("main_area")
)


@app.swap(
    "main_area",
    variants={
        "dir":  [
            Layout()
            .section("dir_heading", pady=(0, 4))
            .section("dir_tree", fill="both", expand=True),
        ],
        "file": [Layout().paired(
            "left_text", "right_text",
            fill=Fill.BOTH, expand=True, sync_yscroll=True,
        )],
    },
    default="dir",
)
def main_area():
    pass


def _init_text(_app: TkApp) -> None:
    app.text_set("left_text", "\n".join(f"left line {i}" for i in range(1, 31)))
    app.text_set("right_text", "\n".join(f"right line {i}" for i in range(1, 31)))
    app.apply_state({
        "dir_rows": [
            ("README.md", "same", "2.1k", "2.1k"),
            ("src/nextpytk/app.py", "diff", "48.3k", "48.9k"),
            ("src/nextpytk/layout.py", "diff", "24.0k", "26.4k"),
            ("src/nextpytk/types.py", "diff", "15.7k", "16.2k"),
            ("src/nextpytk/widgets.py", "same", "2.8k", "2.8k"),
            ("examples/swap_demo.py", "left-only", "3.1k", ""),
            ("tests/test_swap.py", "left-only", "2.4k", ""),
            ("pyproject.toml", "right-only", "", "1.2k"),
            ("ROADMAP.md", "diff", "18.9k", "19.4k"),
            ("LICENSE", "same", "1.1k", "1.1k"),
        ],
    })


if __name__ == "__main__":
    app.run(layout=layout, geometry="720x460", on_ready=_init_text)
