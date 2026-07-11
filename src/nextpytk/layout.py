"""IoC container for layout: inject frame/pack/grid structure into TkApp.

Fluent DSL for arranging widgets registered in TkApp.

Two modes:
- ``.section(...)`` — pack-based section (one Frame, widgets pack inside)
- ``.grid()`` → ``_GridBuilder`` — grid-based placement with ``widget`` / ``end_grid``

Both are chainable: ``Layout().section("a").grid().widget("b").end_grid().section("c")``.

Types from ``nextpytk.types`` provide IDE autocomplete for options.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nextpytk.types import ExpandLike, FillLike, OrientLike, SideLike

if TYPE_CHECKING:
    from nextpytk.app import TkApp


# ── Internal block types (not part of public API) ──

@dataclass
class _Row:
    """Internal: pack-based section block."""
    widgets: list[str]
    side: SideLike = "top"
    fill: FillLike = "x"
    expand: ExpandLike = False
    padx: int = 4
    pady: int = 2
    minsize: int | None = None
    # Per-widget pack opts (for future: individual widget packing hints)
    widget_opts: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class _Paned:
    """Internal: pack a registered ``app.paned`` widget with pane minsizes."""
    name: str
    minsizes: tuple[int, ...] = ()
    weights: tuple[int, ...] = ()
    orient: OrientLike | None = None
    side: SideLike = "top"
    fill: FillLike = "both"
    expand: ExpandLike = True
    padx: int = 4
    pady: int = 2


@dataclass
class _Grid:
    """Internal: grid-based block."""
    cells: dict[str, dict[str, Any]]  # name -> {row, column, sticky, ...}
    padx: int = 4
    pady: int = 2
    fill: FillLike = "x"
    expand: ExpandLike = False
    uniform: str = ""
    # columnconfigure / rowconfigure (applied to frame)
    col_weights: dict[int, int] = field(default_factory=dict)
    col_minsize: dict[int, int] = field(default_factory=dict)
    row_weights: dict[int, int] = field(default_factory=dict)
    row_minsize: dict[int, int] = field(default_factory=dict)


_Block = _Row | _Grid | _Paned


def _pack_section_frame(parent: tk.Misc, block: _Row) -> tk.Frame:
    """Pack a section frame, optionally enforcing ``block.minsize``."""
    if block.minsize is None or block.minsize <= 0:
        frame = tk.Frame(parent)
        frame.pack(
            side="top", fill=block.fill, expand=block.expand,
            padx=block.padx, pady=block.pady,
        )
        return frame

    container = tk.Frame(parent)
    container.pack(
        side="top", fill=block.fill, expand=block.expand,
        padx=block.padx, pady=block.pady,
    )
    if block.fill in ("both", "y"):
        container.grid_rowconfigure(0, weight=1, minsize=block.minsize)
        container.columnconfigure(0, weight=1)
    else:
        container.grid_columnconfigure(0, weight=1, minsize=block.minsize)
        container.rowconfigure(0, weight=1)
    frame = tk.Frame(container)
    frame.grid(row=0, column=0, sticky="nsew")
    return frame


# ── Public API ──

@dataclass
class Layout:
    """Fluent layout DSL. Chain section/grid/apply."""

    _blocks: list[_Block] = field(default_factory=list)

    # ── section (pack) ──

    def section(
        self,
        *widgets: str,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int = 4,
        pady: int = 2,
        minsize: int | None = None,
    ) -> Layout:
        """Add a pack-based section.

        One Frame is created; widgets are pack'ed inside it side-by-side.
        When a single widget is passed, fill/expand also apply to the child.

        ``minsize``: minimum pixels along the grow axis — height for
        ``fill=\"both\"`` / ``fill=\"y\"``, width for ``fill=\"x\"``.
        """
        ws = list(widgets)
        actual_side: SideLike = side
        if len(ws) > 1 and side == "top":
            actual_side = "left"
        self._blocks.append(_Row(
            widgets=ws, side=actual_side, fill=fill,
            expand=expand, padx=padx, pady=pady, minsize=minsize,
        ))
        return self

    def paned(
        self,
        name: str,
        *,
        minsizes: tuple[int, ...] | list[int] = (),
        weights: tuple[int, ...] | list[int] = (),
        orient: OrientLike | None = None,
        side: SideLike = "top",
        fill: FillLike = "both",
        expand: ExpandLike = True,
        padx: int = 4,
        pady: int = 2,
    ) -> Layout:
        """Place a registered ``app.paned(name, ...)`` with per-pane minimum sizes.

        ``minsize`` per pane uses ``tk.PanedWindow`` when any value is ``> 0``
        (``ttk.Panedwindow`` does not support pane ``minsize`` on macOS).

        Example::

            app.paned("workspace", panes=("left", "right"))
            Layout().paned("workspace", minsizes=(160, 240), weights=(1, 2))
        """
        self._blocks.append(_Paned(
            name=name,
            minsizes=tuple(minsizes),
            weights=tuple(weights),
            orient=orient,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        ))
        return self

    # ── factory ──

    @classmethod
    def from_list(cls, widgets: list[str], **kw: Any) -> Layout:
        """Build a layout from a simple list of widget names.

        Each name gets its own pack-based section (one Frame per widget).
        Extra keyword args are forwarded to each ``section()`` call.

        Example::

            layout = Layout.from_list(["title", "timer", "start", "status"])
        """
        layout = cls()
        for name in widgets:
            layout.section(name, **kw)
        return layout

    # ── grid ──

    def grid(
        self,
        *,
        padx: int = 4,
        pady: int = 2,
        fill: FillLike = "x",
        expand: ExpandLike = False,
        uniform: str = "",
    ) -> _GridBuilder:
        """Start a grid block. Returns a fluent builder: ``widget(...)`` → ``end_grid()``.

        Example::

            Layout().grid()
                .widget("name_lbl", sticky="e")
                .widget("name", sticky="ew")
                .next_row()
                .widget("ok", colspan=3)
                .end_grid()
        """
        block = _Grid(
            cells={}, padx=padx, pady=pady,
            fill=fill, expand=expand, uniform=uniform,
        )
        self._blocks.append(block)
        return _GridBuilder(self, block)

    # ── apply (called by TkApp.run) ──

    def widget_names(self) -> set[str]:
        """Return all widget names referenced by this layout."""
        out: set[str] = set()
        for block in self._blocks:
            if isinstance(block, _Row):
                out.update(block.widgets)
            elif isinstance(block, _Paned):
                out.add(block.name)
            elif isinstance(block, _Grid):
                out.update(block.cells.keys())
        return out

    def mount_frames_into(
        self,
        app: TkApp,
        parent: tk.Misc,
        *,
        allowed_widgets: set[str] | None = None,
    ) -> tuple[list[tuple[tk.Frame, _Row]], list[tuple[tk.Frame, _Grid]]]:
        """Create section/grid frames under ``parent`` and map widget masters.

        If ``allowed_widgets`` is provided, every referenced widget name must be
        included in the set; otherwise a ``ValueError`` is raised.
        """
        row_jobs: list[tuple[tk.Frame, _Row]] = []
        grid_jobs: list[tuple[tk.Frame, _Grid]] = []
        app._layout_paned_opts = {}

        def _ensure_allowed(name: str) -> None:
            if allowed_widgets is not None and name not in allowed_widgets:
                raise ValueError(f"Widget '{name}' is not allowed in this view layout")

        for block in self._blocks:
            if isinstance(block, _Row):
                frame = _pack_section_frame(parent, block)
                for name in block.widgets:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                row_jobs.append((frame, block))
            elif isinstance(block, _Paned):
                _ensure_allowed(block.name)
                frame = tk.Frame(parent)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx, pady=block.pady,
                )
                app._widget_masters[block.name] = frame
                opts: dict[str, Any] = {
                    "minsizes": block.minsizes,
                    "weights": block.weights,
                }
                if block.orient is not None:
                    opts["orient"] = block.orient
                app._layout_paned_opts[block.name] = opts
                row_jobs.append((frame, _Row(
                    widgets=[block.name],
                    side="top",
                    fill=block.fill,
                    expand=block.expand,
                )))
            elif isinstance(block, _Grid):
                frame = tk.Frame(parent)
                frame.pack(
                    side="top", fill=block.fill, expand=block.expand,
                    padx=block.padx, pady=block.pady,
                )
                for col, w in block.col_weights.items():
                    frame.columnconfigure(col, weight=w, uniform=block.uniform or "")
                for col, ms in block.col_minsize.items():
                    frame.columnconfigure(col, minsize=ms)
                for row, w in block.row_weights.items():
                    frame.rowconfigure(row, weight=w)
                for row, ms in block.row_minsize.items():
                    frame.rowconfigure(row, minsize=ms)
                for name in block.cells:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                grid_jobs.append((frame, block))

        return row_jobs, grid_jobs

    def pack_children_for(
        self,
        app: TkApp,
        row_jobs: list[tuple[tk.Frame, _Row]],
        grid_jobs: list[tuple[tk.Frame, _Grid]],
    ) -> None:
        """Pack/grid children for jobs returned by ``mount_frames_into``."""
        for _frame, row in row_jobs:
            n = len(row.widgets)
            for name in row.widgets:
                tk_w = app._tk_widgets.get(name)
                if tk_w is None:
                    continue
                if n == 1:
                    tk_w.pack(side=row.side, padx=2, pady=1,
                              fill=row.fill, expand=row.expand)
                else:
                    tk_w.pack(side=row.side, padx=2, pady=1)
        for _frame, gb in grid_jobs:
            for name, opts in gb.cells.items():
                tk_w = app._tk_widgets.get(name)
                if tk_w is None:
                    continue
                grid_opts = {k: v for k, v in opts.items()
                             if k in ("row", "column", "sticky", "padx", "pady",
                                      "columnspan", "rowspan")}
                tk_w.grid(**grid_opts)

    def mount_frames(self, app: TkApp) -> None:
        """Create section Frames on root, register widget→parent mapping."""
        app._row_pack_jobs = []
        app._grid_pack_jobs = []
        app._widget_masters = {}
        app._layout_paned_opts = {}
        root = app._root
        if root is None:
            raise RuntimeError("Tk root is not initialized. Set app._root before mounting.")
        row_jobs, grid_jobs = self.mount_frames_into(app, root)
        app._row_pack_jobs = row_jobs
        app._grid_pack_jobs = grid_jobs

    def pack_children(self, app: TkApp) -> None:
        """Pack/grid children inside their section frames."""
        self.pack_children_for(app, app._row_pack_jobs, app._grid_pack_jobs)


# ── Fluent grid builder ──

class _GridBuilder:
    """Fluent sub-DSL for grid layout.

    Chain ``widget(...)`` calls, advance with ``next_row()`` / ``next_col()``,
    configure with ``col_weight(...)`` / ``row_weight(...)``, return to ``Layout``
    with ``end_grid()``.

    All methods return self for chaining.
    """

    def __init__(self, layout: Layout, block: _Grid):
        self._layout = layout
        self._block = block
        self._row = 0
        self._col = 0
        self._colspan = 1

    # ── navigation ──

    def next_row(self) -> _GridBuilder:
        """Advance to next row, reset column to 0."""
        self._row += 1
        self._col = 0
        self._colspan = 1
        return self

    def next_col(self, n: int = 1) -> _GridBuilder:
        """Skip n columns ahead."""
        self._col += n
        self._colspan = 1
        return self

    def at(self, row: int, col: int) -> _GridBuilder:
        """Jump to absolute (row, col)."""
        self._row = row
        self._col = col
        self._colspan = 1
        return self

    # ── placement ──

    def widget(
        self,
        name: str,
        *,
        sticky: str = "",
        padx: int = 2,
        pady: int = 1,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> _GridBuilder:
        """Place a widget at the current cursor position, then advance column.

        ``colspan`` overrides any previously-set colspan (via ``.span(...)``).
        """
        cs = colspan if colspan is not None else self._colspan
        opts: dict[str, Any] = {
            "row": self._row, "column": self._col,
            "sticky": sticky, "padx": padx, "pady": pady,
        }
        if cs > 1:
            opts["columnspan"] = cs
        if rowspan > 1:
            opts["rowspan"] = rowspan
        self._block.cells[name] = opts
        self._col += cs
        self._colspan = 1
        return self

    # ── span preset ──

    def span(self, cols: int) -> _GridBuilder:
        """Set column span for the **next** ``widget(...)`` call."""
        self._colspan = cols
        return self

    # ── column/row configure ──

    def col_weights(self, *weights: int) -> _GridBuilder:
        """Set column weights by position: ``col_weights(0, 1, 1)`` → col 0 weight=0, col 1 weight=1, col 2 weight=1."""
        for i, w in enumerate(weights):
            self._block.col_weights[i] = w
        return self

    def row_weights(self, *weights: int) -> _GridBuilder:
        """Set row weights by position: ``row_weights(0, 1)`` → row 0 weight=0, row 1 weight=1."""
        for i, w in enumerate(weights):
            self._block.row_weights[i] = w
        return self

    def col_weight(self, col: int, weight: int = 1) -> _GridBuilder:
        """Set ``columnconfigure(col, weight=...)``. Prefer ``col_weights(...)`` for bulk."""
        self._block.col_weights[col] = weight
        return self

    def col_minsize(self, col: int, minsize: int) -> _GridBuilder:
        """Set ``columnconfigure(col, minsize=...)``."""
        self._block.col_minsize[col] = minsize
        return self

    def row_weight(self, row: int, weight: int = 1) -> _GridBuilder:
        """Set ``rowconfigure(row, weight=...)``. Prefer ``row_weights(...)`` for bulk."""
        self._block.row_weights[row] = weight
        return self

    def row_minsize(self, row: int, minsize: int) -> _GridBuilder:
        """Set ``rowconfigure(row, minsize=...)``."""
        self._block.row_minsize[row] = minsize
        return self

    # ── exit ──

    def end_grid(self) -> Layout:
        """Finish grid block, return to Layout DSL."""
        return self._layout


# ── Context-manager LayoutBuilder ──

class LayoutBuilder:
    """Context-manager API for declarative layout construction.

    Build layouts with ``with`` blocks instead of chaining::

        builder = LayoutBuilder()
        with builder:
            builder.section("title")
            with builder.grid(col_weights=(0, 1)):
                builder.widget("celsius", sticky="ew")
                builder.widget("fahrenheit", sticky="ew")
                builder.next_row().span(2).widget("note")
        layout = builder.build()

    ``LayoutBuilder`` produces a ``Layout`` that can be passed to
    ``app.run(layout=...)`` or ``view_layouts``.
    """

    def __init__(self) -> None:
        self._layout = Layout()
        self._stack: list[_GridBuilder | Layout] = [self._layout]

    # ── with-block entry/exit ──

    def __enter__(self) -> LayoutBuilder:
        return self

    def __exit__(self, *args: object) -> None:
        # Balance any unclosed grid blocks.
        while len(self._stack) > 1:
            self._pop_grid()

    # ── section ──

    def section(
        self,
        *widgets: str,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int = 4,
        pady: int = 2,
        minsize: int | None = None,
    ) -> None:
        """Add a pack-based section to the layout."""
        self._layout.section(
            *widgets, side=side, fill=fill,
            expand=expand, padx=padx, pady=pady, minsize=minsize,
        )

    def paned(
        self,
        name: str,
        *,
        minsizes: tuple[int, ...] | list[int] = (),
        weights: tuple[int, ...] | list[int] = (),
        orient: OrientLike | None = None,
        side: SideLike = "top",
        fill: FillLike = "both",
        expand: ExpandLike = True,
        padx: int = 4,
        pady: int = 2,
    ) -> None:
        """Place ``app.paned(name)`` with per-pane ``minsizes`` (see ``Layout.paned``)."""
        self._layout.paned(
            name,
            minsizes=minsizes,
            weights=weights,
            orient=orient,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        )

    # ── grid block (context manager) ──

    def grid(
        self,
        *,
        padx: int = 4,
        pady: int = 2,
        fill: FillLike = "x",
        expand: ExpandLike = False,
        uniform: str = "",
        col_weights: tuple[int, ...] = (),
        row_weights: tuple[int, ...] = (),
    ) -> LayoutBuilder:
        """Enter a grid block. Returns self for ``with ... as ...`` use.

        Example::

            with builder.grid(col_weights=(1, 2)):
                builder.widget("a")
                builder.widget("b")
        """
        block = _Grid(
            cells={}, padx=padx, pady=pady,
            fill=fill, expand=expand, uniform=uniform,
        )
        for i, w in enumerate(col_weights):
            block.col_weights[i] = w
        for i, w in enumerate(row_weights):
            block.row_weights[i] = w
        self._layout._blocks.append(block)
        gb = _GridBuilder(self._layout, block)
        self._stack.append(gb)
        return self

    # ── grid-builder methods (delegated when inside grid) ──

    def _current_grid(self) -> _GridBuilder:
        """Return the innermost _GridBuilder on the stack."""
        for item in reversed(self._stack):
            if isinstance(item, _GridBuilder):
                return item
        raise RuntimeError("widget() / next_row() only valid inside grid block")

    def _pop_grid(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    def __exit__grid(self) -> None:
        """Called by with-block __exit__ when a grid block ends."""
        self._pop_grid()

    def widget(
        self,
        name: str,
        *,
        sticky: str = "",
        padx: int = 2,
        pady: int = 1,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> None:
        """Place a widget at the current grid cursor."""
        self._current_grid().widget(
            name, sticky=sticky, padx=padx, pady=pady,
            colspan=colspan, rowspan=rowspan,
        )

    def next_row(self) -> LayoutBuilder:
        """Advance grid cursor to next row."""
        self._current_grid().next_row()
        return self

    def next_col(self, n: int = 1) -> LayoutBuilder:
        """Skip grid cursor forward n columns."""
        self._current_grid().next_col(n)
        return self

    def at(self, row: int, col: int) -> LayoutBuilder:
        """Jump grid cursor to absolute (row, col)."""
        self._current_grid().at(row, col)
        return self

    def span(self, cols: int) -> LayoutBuilder:
        """Set column span for the next widget() call."""
        self._current_grid().span(cols)
        return self

    # ── build ──

    def build(self) -> Layout:
        """Finalize and return the Layout."""
        while len(self._stack) > 1:
            self._pop_grid()
        return self._layout
