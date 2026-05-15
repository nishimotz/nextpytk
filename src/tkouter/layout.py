"""IoC container for layout: inject frame/pack/grid structure into TkApp.

Fluent DSL for arranging widgets registered in TkApp.

Two modes:
- ``.section(...)`` — pack-based section (one Frame, widgets pack inside)
- ``.grid()`` → ``_GridBuilder`` — grid-based placement with ``widget`` / ``end_grid``

Both are chainable: ``Layout().section("a").grid().widget("b").end_grid().section("c")``.

Types from ``tkouter.types`` provide IDE autocomplete for options.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkouter.types import ExpandLike, FillLike, SideLike

if TYPE_CHECKING:
    from tkouter.app import TkApp


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
    # Per-widget pack opts (for future: individual widget packing hints)
    widget_opts: dict[str, dict[str, Any]] = field(default_factory=dict)


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


_Block = _Row | _Grid


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
    ) -> Layout:
        """Add a pack-based section.

        One Frame is created; widgets are pack'ed inside it side-by-side.
        When a single widget is passed, fill/expand also apply to the child.
        """
        ws = list(widgets)
        actual_side: SideLike = side
        if len(ws) > 1 and side == "top":
            actual_side = "left"
        self._blocks.append(_Row(
            widgets=ws, side=actual_side, fill=fill,
            expand=expand, padx=padx, pady=pady,
        ))
        return self

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

        def _ensure_allowed(name: str) -> None:
            if allowed_widgets is not None and name not in allowed_widgets:
                raise ValueError(f"Widget '{name}' is not allowed in this view layout")

        for block in self._blocks:
            if isinstance(block, _Row):
                frame = tk.Frame(parent)
                frame.pack(
                    side="top", fill=block.fill, expand=block.expand,
                    padx=block.padx, pady=block.pady,
                )
                for name in block.widgets:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                row_jobs.append((frame, block))
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
