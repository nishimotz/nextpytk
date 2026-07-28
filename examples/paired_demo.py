"""Layout.paired() demo — side-by-side compare without app.paned.

Two text widgets share a single paired frame.  The left pane is read-only and
highlights "DIFF" lines; the right pane is editable.  Scrolling either pane
moves the other because ``Layout().paired(..., sync_yscroll=True)`` wires
their y-views together.
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

app = TkApp(title="Paired layout demo")


def _make_text(base: str) -> str:
    lines = []
    for i in range(1, 41):
        marker = "original" if i % 5 != 0 else "DIFF"
        lines.append(f"Line {i}: {base} {marker}")
    return "\n".join(lines)


LEFT_TEXT = _make_text("left pane")
RIGHT_TEXT = _make_text("right pane")


@app.status("info")
def info() -> str:
    return "Paired layout: scroll one text widget, both move"


@app.text(
    "left_text",
    readonly=True,
    tags={"diff": {"foreground": "#d32f2f", "background": "#ffebee"}},
    takefocus=True,
)
def on_left(value: str) -> dict[str, str]:
    return {}


@app.text("right_text", takefocus=True)
def on_right(value: str) -> dict[str, str]:
    return {"info": f"Characters: {len(value)}"}


layout = (
    Layout()
    .section("info")
    .paired(
        "left_text",
        "right_text",
        weight=(1, 1),
        fill=Fill.BOTH,
        expand=True,
        sync_yscroll=True,
    )
)


def _init_text(_app: TkApp) -> None:
    app.text_set("left_text", LEFT_TEXT)
    app.text_set("right_text", RIGHT_TEXT)
    for i in range(5, 41, 5):
        app.text_tag_add("left_text", "diff", f"{i}.0", f"{i + 1}.0")


if __name__ == "__main__":
    app.run(layout=layout, geometry="640x360", on_ready=_init_text)
