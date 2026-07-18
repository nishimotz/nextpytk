"""nextpytk paned sample — horizontal split with ``with app.pane(...)``."""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import Fill, Orient

app = TkApp(title="Paned split")

app.paned(
    "workspace",
    panes=("left", "right"),
    orient=Orient.HORIZONTAL,
    weights=(1, 2),
    description="Horizontal split (drag the sash to resize)",
)


@app.status("hint")
def hint() -> str:
    return "Drag the center divider to change pane widths"


with app.pane("left"):
    @app.label("left_title")
    def left_title() -> str:
        return "Left pane"

    @app.message("left_body")
    def left_body() -> str:
        return "Content in the left pane.\nFor a comparison tool, place a Location list here."


with app.pane("right"):
    @app.label("right_title")
    def right_title() -> str:
        return "Right pane"

    @app.message("right_body")
    def right_body() -> str:
        return "Content in the right pane.\nUse as a placeholder for a text comparison pane."


layout = (
    Layout()
    .section("hint")
    .paned("workspace", minsizes=(160, 200), weights=(1, 2), fill=Fill.BOTH, expand=True)
)

if __name__ == "__main__":
    app.run(layout=layout, geometry="520x320")
