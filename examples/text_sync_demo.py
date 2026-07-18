"""nextpytk text sync demo — tag config, read-only, paired y-scroll.

Two text panes side-by-side: the left pane is read-only and highlights
differences in red; the right pane is editable. Both panes scroll together.
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import Fill, Orient

app = TkApp(title="Text sync demo")

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
    return "Scroll either pane — both move together"


app.paned(
    "workspace",
    panes=("left", "right"),
    orient=Orient.HORIZONTAL,
    weights=(1, 1),
    description="Two synchronized text panes",
)


with app.pane("left"):
    @app.text(
        "left_text",
        readonly=True,
        tags={"diff": {"foreground": "#d32f2f", "background": "#ffebee"}},
        sync_yscroll_with="right_text",
        takefocus=True,
    )
    def on_left(value: str) -> dict[str, str]:
        return {}


with app.pane("right"):
    @app.text(
        "right_text",
        sync_yscroll_with="left_text",
        takefocus=True,
    )
    def on_right(value: str) -> dict[str, str]:
        return {"info": f"Characters: {len(value)}"}


layout = (
    Layout()
    .section("info")
    .paned("workspace", weights=(1, 1), fill=Fill.BOTH, expand=True)
)


def _init_text(_app: TkApp) -> None:
    # Populate both panes. text_set works even for the read-only left pane.
    app.text_set("left_text", LEFT_TEXT)
    app.text_set("right_text", RIGHT_TEXT)
    # Highlight every 5th line in the read-only left pane.
    for i in range(5, 41, 5):
        app.text_tag_add("left_text", "diff", f"{i}.0", f"{i + 1}.0")


if __name__ == "__main__":
    app.run(layout=layout, geometry="640x360", on_ready=_init_text)
