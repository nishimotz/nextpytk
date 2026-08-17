"""Layout.flow demo — Flutter-style custom flow positioning.

``flow`` positions children via a ``FlowDelegate`` (Flutter ``Flow`` analog).
The delegate decides each child's (x, y, width, height) from the available
``Constraints``; here a ``CircleDelegate`` lays children around a circle whose
radius follows the available space. This is a layout ``Layout.grid()`` cannot
express — the positions are computed, not declared.

Resize the window to watch the circle grow and shrink.
"""

import math

from nextpytk import TkApp, Layout, FlowDelegate, Constraints, tokens
from nextpytk.types import Fill

app = TkApp(title="Flow Demo")


@app.status("msg")
def msg():
    return "Resize to grow/shrink the circle"


@app.button("tile1", label="Tile 1")
@app.button("tile2", label="Tile 2")
@app.button("tile3", label="Tile 3")
@app.button("tile4", label="Tile 4")
@app.button("tile5", label="Tile 5")
@app.button("tile6", label="Tile 6")
def on_tile(values):
    return {}


class CircleDelegate(FlowDelegate):
    """Flow delegate that lays children around a circle.

    Each child is centered on the circumference of a circle whose radius is
    derived from the available width/height. This is a layout ``grid`` cannot
    express: positions are computed from the constraints, not declared as
    (row, column) cells.
    """

    def _cell(self, children: list[str], constraints: Constraints) -> tuple[int, int]:
        """Largest natural (width, height) among children, as a cell size."""
        w = max(
            constraints.sizes.get(name, (1, tokens.MIN_TARGET))[0]
            for name in children
        )
        h = max(
            constraints.sizes.get(name, (1, tokens.MIN_TARGET))[1]
            for name in children
        )
        return w, h

    def compute_positions(
        self,
        children: list[str],
        constraints: Constraints,
    ) -> dict[str, tuple[int, int, int, int]]:
        cell_w, cell_h = self._cell(children, constraints)
        n = len(children)
        # Radius shrinks to fit the largest child on the circumference while
        # staying inside the available box.
        radius = max(
            cell_w,
            min(constraints.width, constraints.height) // 2 - cell_h,
        )
        cx = constraints.width / 2
        cy = constraints.height / 2
        return {
            name: (
                round(cx + radius * math.cos(2 * math.pi * i / n) - cell_w / 2),
                round(cy + radius * math.sin(2 * math.pi * i / n) - cell_h / 2),
                cell_w,
                cell_h,
            )
            for i, name in enumerate(children)
        }

    def compute_height(
        self,
        children: list[str],
        constraints: Constraints,
    ) -> int:
        cell_w, cell_h = self._cell(children, constraints)
        return 2 * (min(constraints.width, constraints.height) // 2) + cell_h


app.run(
    geometry="480x480",
    layout=Layout(spacing=2)
    .section("msg")
    # flow: CircleDelegate positions tiles around a circle, recomputed on resize.
    .flow(
        "tile1", "tile2", "tile3", "tile4", "tile5", "tile6",
        delegate=CircleDelegate(),
        fill=Fill.X,
        pady=12,
    )
)
