"""Layout.wrap / Layout.flow demo — Flutter-style wrapping, flex, and flow.

Four blocks demonstrate the Flutter-derived layout vocabulary added in 0.5:

1. ``wrap`` — a wrapping flow (Flutter ``Wrap`` analog). Widgets fill a row
   left-to-right and wrap onto the next row when they no longer fit. Width is
   content-driven; ``gapx``/``gapy`` (SPACE tokens) control in-row and
   row-to-row spacing. This is the successor to the pre-0.5 ``cluster``.

2. ``wrap`` + ``Flex`` — a wrap child that absorbs leftover horizontal space in
   its row (Flutter ``Expanded`` analog). Here the ``search`` entry grows to
   fill the gap between the two buttons while the buttons keep their natural
   width.

3. ``wrap`` — checkboxes reflow independently.

4. ``flow`` — custom positioning via a ``FlowDelegate`` (Flutter ``Flow``
   analog). The delegate decides each child's (x, y, width, height) from the
   available ``Constraints``; here a ``GridDelegate`` lays children into a
   fixed column grid and is recomputed on resize.

Resize the window to watch wrap reflow and the flow grid re-center.
"""

from nextpytk import TkApp, Layout, Flex, FlowDelegate, Constraints
from nextpytk.types import Fill

app = TkApp(title="Wrap / Flex / Flow Demo")


@app.status("msg")
def msg():
    return "Type and click around"


@app.button("greet", label="Greet")
def on_greet(values):
    name = values.get("name") or "world"
    return {"msg": f"Hello, {name}!"}


@app.button("clear", label="Clear")
def on_clear(values):
    return {"msg": "Cleared", "name": "", "active": False}


@app.button("upper", label="Upper")
def on_upper(values):
    name = (values.get("name") or "").upper()
    return {"name": name, "msg": f"Now: {name}"}


@app.button("ok", label="OK")
def on_ok(values):
    return {"msg": "OK"}


@app.entry("name", placeholder="Name", width=30)
def on_name(value):
    return {}


@app.entry("search", placeholder="Search terms", width=30)
def on_search(value):
    return {}


@app.button("filter", label="Filter")
def on_filter(values):
    return {"msg": "Filtered"}


@app.checkbutton("active", text="Active")
def on_active(value):
    return {"msg": f"active={value}"}


@app.checkbutton("verbose", text="Verbose")
def on_verbose(value):
    return {"msg": f"verbose={value}"}


@app.checkbutton("confirm", text="Confirm")
def on_confirm(value):
    return {"msg": f"confirm={value}"}


@app.button("tile1", label="Tile 1")
@app.button("tile2", label="Tile 2")
@app.button("tile3", label="Tile 3")
@app.button("tile4", label="Tile 4")
def on_tile(values):
    return {}


class GridDelegate(FlowDelegate):
    """Flow delegate that lays children into a fixed number of columns.

    Cell height is taken from the largest child's natural height (provided by
    the library via ``constraints.sizes``) so labels are never clipped and
    rows are spaced to match the actual content height.
    """

    def __init__(self, cols: int, gap: int = 1):
        self.cols = cols
        self.gap = gap

    def _cell_h(self, children: list[str], constraints: Constraints) -> int:
        return max(
            constraints.sizes.get(name, (1, 44))[1]
            for name in children
        ) or 44

    def compute_positions(
        self,
        children: list[str],
        constraints: Constraints,
    ) -> dict[str, tuple[int, int, int, int]]:
        from nextpytk import tokens as t

        gap = t.SPACE[self.gap]
        cell_w = (constraints.width - gap * (self.cols - 1)) // self.cols
        cell_h = self._cell_h(children, constraints)
        return {
            name: (
                (i % self.cols) * (cell_w + gap),
                (i // self.cols) * (cell_h + gap),
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
        from nextpytk import tokens as t

        gap = t.SPACE[self.gap]
        rows = (len(children) + self.cols - 1) // self.cols
        cell_h = self._cell_h(children, constraints)
        return rows * cell_h + (rows - 1) * gap


# Shared vertical rhythm across the blocks.
# Align wrap gapy with flow GridDelegate gap for consistent vertical spacing.
_GAPY = 2  # SPACE[2] = 8px to match GridDelegate(cols=2, gap=2)
_PADY = 12

app.run(
    layout=Layout(spacing=2)
    .section("msg")
    # 1. wrap: buttons + entry reflow onto new rows as the window narrows.
    .wrap(
        "greet", "name", "upper", "clear",
        fill=Fill.X,
        gapx=2,   # SPACE[2] = 8px horizontal gap
        gapy=_GAPY,
        pady=_PADY,
    )
    # 2. wrap + Flex: the search entry absorbs leftover width in its row.
    .wrap(
        "filter",
        Flex("search", flex=2),
        "ok",
        fill=Fill.X,
        gapx=2,
        gapy=_GAPY,
        pady=_PADY,
    )
    # 3. wrap: checkboxes reflow independently.
    .wrap(
        "active", "verbose", "confirm",
        fill=Fill.X,
        gapx=1,
        gapy=_GAPY,
        pady=_PADY,
    )
    # 4. flow: GridDelegate positions tiles into 2 columns, recomputed on resize.
    .flow(
        "tile1", "tile2", "tile3", "tile4",
        delegate=GridDelegate(cols=2, gap=2),
        fill=Fill.X,
        pady=_PADY,
    )
)
