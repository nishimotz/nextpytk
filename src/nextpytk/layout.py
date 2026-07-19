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
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nextpytk import tokens as _t
from nextpytk.types import AnchorLike, ExpandLike, FillLike, OrientLike, SideLike

# Layout spacing defaults come from the token scale (tokens.SPACE) — the
# design system forbids bare pixel integers. Sections carry the vertical
# rhythm (adjacent gap = 2 * _PAD); children add none of their own.
_PAD = _t.SPACE[1]

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
    padx: int = _PAD
    pady: int = _PAD
    minsize: int | None = None
    anchor: AnchorLike | None = None
    # Per-widget pack opts (for future: individual widget packing hints)
    widget_opts: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Extra markers consumed by chrome helpers (e.g. Kizashi header/status).
    extras: dict[str, Any] = field(default_factory=dict)


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
    padx: int = _PAD
    pady: int = _PAD


@dataclass
class _Grid:
    """Internal: grid-based block."""
    cells: dict[str, dict[str, Any]]  # name -> {row, column, sticky, ...}
    padx: int = _PAD
    pady: int = _PAD
    fill: FillLike = "x"
    expand: ExpandLike = False
    uniform: str = ""
    # columnconfigure / rowconfigure (applied to frame)
    col_weights: dict[int, int] = field(default_factory=dict)
    col_minsize: dict[int, int] = field(default_factory=dict)
    row_weights: dict[int, int] = field(default_factory=dict)
    row_minsize: dict[int, int] = field(default_factory=dict)


_Block = _Row | _Grid | _Paned


def _section_anchor(block: _Row) -> AnchorLike | None:
    """Effective pack anchor for a section frame.

    Pack centers a non-filling widget in its parcel, so a ``fill="none"``
    section floats to the middle no matter how its children are anchored.
    Default to west for the Kizashi left-aligned hierarchy;
    ``section(anchor=...)`` overrides (e.g. ``anchor="center"``).
    """
    if block.anchor is not None:
        return block.anchor
    if block.fill in ("none", "y"):
        return "w"
    return None


def _pack_section_frame(parent: tk.Misc, block: _Row) -> tk.Frame:
    """Pack a section frame, optionally enforcing ``block.minsize``."""
    pack_kw: dict[str, Any] = {
        "side": "top", "fill": block.fill, "expand": block.expand,
        "padx": block.padx, "pady": block.pady,
    }
    anchor = _section_anchor(block)
    if anchor:
        pack_kw["anchor"] = anchor

    frame = tk.Frame(parent)
    frame.pack(**pack_kw)

    # ``minsize`` reserves space along the grow axis. When a previous sibling
    # already consumed all available room via ``expand=True`` the packer would
    # otherwise collapse this frame to 1x1, so we disable propagation and give
    # the frame a concrete size.
    if block.minsize is not None and block.minsize > 0:
        frame.pack_propagate(False)
        if block.fill in ("both", "y"):
            frame.configure(height=block.minsize)
        else:
            frame.configure(height=block.minsize)

    return frame


# ── Public API ──

@dataclass
class Layout:
    """Fluent layout DSL. Chain section/grid/apply.

    When the Kizashi design system is active (the default in ``TkApp``),
    ``Layout`` wraps the root in a ``content_frame`` with the standard page
    margin and paints every section frame with the Kizashi ground color.
    ``.header()`` and ``.status()`` create chrome (title block and bottom bar).
    Pass ``theme=False`` to ``TkApp`` or build widgets manually to keep the
    platform-default look.
    """

    _blocks: list[_Block] = field(default_factory=list)

    # Sentinel names used by chrome helpers; they are never registered as
    # real widgets, so they cannot collide with user widget names.
    _HEADER = "__kizashi_header__"
    _STATUS = "__kizashi_status__"

    # ── section (pack) ──

    def section(
        self,
        *widgets: str,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int = _PAD,
        pady: int = _PAD,
        minsize: int | None = None,
        anchor: AnchorLike | None = None,
    ) -> Layout:
        """Add a pack-based section.

        One Frame is created; widgets are pack'ed inside it side-by-side.
        When a single widget is passed, fill/expand also apply to the child.

        ``minsize``: minimum pixels along the grow axis — height for
        ``fill=\"both\"`` / ``fill=\"y\"``, width for ``fill=\"x\"``.
        ``anchor``: where a non-filling section sits in the window.
        Defaults to ``\"w\"`` (left) for ``fill=\"none\"`` / ``\"y\"`` —
        pass ``anchor=\"center\"`` to center it.
        """
        ws = list(widgets)
        actual_side: SideLike = side
        if len(ws) > 1 and side == "top":
            actual_side = "left"
        self._blocks.append(_Row(
            widgets=ws, side=actual_side, fill=fill,
            expand=expand, padx=padx, pady=pady, minsize=minsize,
            anchor=anchor,
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
        padx: int = _PAD,
        pady: int = _PAD,
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
        padx: int = _PAD,
        pady: int = _PAD,
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

        # When the root is a true top-level window (run/run_async), wrap the
        # layout in a content frame so the Kizashi ground color and page
        # margin apply even to the simplest Layout.from_list() examples.
        from nextpytk.theme import content_frame, window_header, status_bar
        from nextpytk import tokens as t
        is_toplevel = isinstance(parent, tk.Tk) or getattr(parent, "winfo_toplevel", lambda: parent)() is parent
        if is_toplevel:
            body = content_frame(parent, padding=t.SPACE[6])
        else:
            # View/tab pages breathe too: inner content margin so sections
            # don't hug the notebook border (SPACE[6] / 24px page pad).
            body = tk.Frame(parent, bg=t.BG, bd=0, highlightthickness=0)
            body.pack(fill="both", expand=True,
                      padx=t.SPACE[6], pady=t.SPACE[4])

        for block in self._blocks:
            if isinstance(block, _Row):
                frame = _pack_section_frame(body, block)
                extras = block.extras if isinstance(block, _Row) else {}
                if isinstance(extras, dict):
                    if "kizashi_header" in extras:
                        title, subtitle = extras["kizashi_header"]
                        window_header(frame, title, subtitle)
                        row_jobs.append((frame, block))
                        continue
                    if "kizashi_status" in extras:
                        name = extras["kizashi_status"]
                        lbl = status_bar(frame)
                        app._tk_widgets[name] = lbl
                        app._widget_masters[name] = frame
                        row_jobs.append((frame, block))
                        continue
                for name in block.widgets:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
                row_jobs.append((frame, block))
            elif isinstance(block, _Paned):
                _ensure_allowed(block.name)
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx, pady=block.pady,
                )
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
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
                frame = tk.Frame(body)
                frame.pack(
                    side="top", fill=block.fill, expand=block.expand,
                    padx=block.padx, pady=block.pady,
                )
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
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
                    tk_w.pack(side=row.side, padx=0, pady=0,
                              fill=row.fill, expand=row.expand)
                else:
                    # horizontal gap between siblings only (section frame
                    # already carries the outer rhythm). Last child hugs the
                    # right edge; all children share the available space when
                    # expand=True.
                    is_last = name == row.widgets[-1]
                    tk_w.pack(
                        side=row.side,
                        padx=(0, 0 if is_last else _PAD), pady=0,
                        fill=row.fill,
                        expand=row.expand,
                    )
        # ``minsize`` must be a lower bound, not a hardcoded size.  If a child
        # naturally needs more space (e.g. a themed button), grow the section
        # frame so the child is not clipped.  This lets callers drop ``minsize``
        # for simple fixed-height widgets and still get readable output.
        for frame, row in row_jobs:
            if row.minsize is None or row.minsize <= 0:
                continue
            if row.fill in ("both", "y"):
                continue
            natural = max(
                (c.winfo_reqheight() for c in frame.winfo_children()), default=0
            )
            target = max(row.minsize, natural)
            if target > row.minsize:
                frame.pack_propagate(False)
                frame.configure(height=target)

        for _frame, gb in grid_jobs:
            for name, opts in gb.cells.items():
                tk_w = app._tk_widgets.get(name)
                if tk_w is None:
                    continue
                grid_opts = {k: v for k, v in opts.items()
                             if k in ("row", "column", "sticky", "padx", "pady",
                                      "columnspan", "rowspan")}
                tk_w.grid(**grid_opts)

    def header(self, title: str, subtitle: str | None = None) -> Layout:
        """Reserve a top-of-window header area rendered by ``window_header``.

        The header is styled automatically by the Kizashi design system.
        """
        self._blocks.append(_Row(
            widgets=[self._HEADER],
            side="top",
            fill="x",
            expand=False,
            padx=0,
            pady=0,
            extras={"kizashi_header": (title, subtitle)},
        ))
        return self

    def status(self, name: str) -> Layout:
        """Place a widget in a bottom status bar."""
        self._blocks.append(_Row(
            widgets=[name],
            side="top",
            fill="x",
            expand=False,
            padx=0,
            pady=0,
            extras={"kizashi_status": name},
        ))
        return self

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
        padx: int = _PAD,
        pady: int = _PAD,
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
        """Deprecated in 0.4.1. Use ``col_weight(col, weight)`` instead.

        Previously this set column weights by position:
        ``col_weights(0, 1, 1)`` → col 0 weight=0, col 1 weight=1, col 2 weight=1.
        The index-order semantics were easy to misuse, so the plural bulk API is
        being removed in 0.5.0.
        """
        warnings.warn(
            "col_weights() is deprecated; use col_weight(col, weight) instead. "
            "Plural bulk methods will be removed in nextpytk 0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for i, w in enumerate(weights):
            self.col_weight(i, w)
        return self

    def row_weights(self, *weights: int) -> _GridBuilder:
        """Deprecated in 0.4.1. Use ``row_weight(row, weight)`` instead.

        Previously this set row weights by position:
        ``row_weights(0, 1)`` → row 0 weight=0, row 1 weight=1.
        The index-order semantics were easy to misuse, so the plural bulk API is
        being removed in 0.5.0.
        """
        warnings.warn(
            "row_weights() is deprecated; use row_weight(row, weight) instead. "
            "Plural bulk methods will be removed in nextpytk 0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for i, w in enumerate(weights):
            self.row_weight(i, w)
        return self

    def col_weight(self, col: int, weight: int = 1) -> _GridBuilder:
        """Set ``columnconfigure(col, weight=...)``."""
        self._block.col_weights[col] = weight
        return self

    def col_minsizes(self, *minsizes: int) -> _GridBuilder:
        """Deprecated in 0.4.1. Use ``col_minsize(col, minsize)`` instead."""
        warnings.warn(
            "col_minsizes() is deprecated; use col_minsize(col, minsize) instead. "
            "Plural bulk methods will be removed in nextpytk 0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for i, ms in enumerate(minsizes):
            self.col_minsize(i, ms)
        return self

    def col_minsize(self, col: int, minsize: int) -> _GridBuilder:
        """Set ``columnconfigure(col, minsize=...)``."""
        self._block.col_minsize[col] = minsize
        return self

    def row_weight(self, row: int, weight: int = 1) -> _GridBuilder:
        """Set ``rowconfigure(row, weight=...)``."""
        self._block.row_weights[row] = weight
        return self

    def row_minsizes(self, *minsizes: int) -> _GridBuilder:
        """Deprecated in 0.4.1. Use ``row_minsize(row, minsize)`` instead."""
        warnings.warn(
            "row_minsizes() is deprecated; use row_minsize(row, minsize) instead. "
            "Plural bulk methods will be removed in nextpytk 0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for i, ms in enumerate(minsizes):
            self.row_minsize(i, ms)
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
            with builder.grid():
                builder.col_weight(0, 0).col_weight(1, 1)
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
        padx: int = _PAD,
        pady: int = _PAD,
        minsize: int | None = None,
        anchor: AnchorLike | None = None,
    ) -> None:
        """Add a pack-based section to the layout."""
        self._layout.section(
            *widgets, side=side, fill=fill,
            expand=expand, padx=padx, pady=pady, minsize=minsize,
            anchor=anchor,
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
        padx: int = _PAD,
        pady: int = _PAD,
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
        padx: int = _PAD,
        pady: int = _PAD,
        fill: FillLike = "x",
        expand: ExpandLike = False,
        uniform: str = "",
        col_weights: tuple[int, ...] = (),
        row_weights: tuple[int, ...] = (),
    ) -> LayoutBuilder:
        """Enter a grid block. Returns self for ``with ... as ...`` use.

        Example::

            with builder.grid():
                builder.col_weight(0, 0).col_weight(1, 1)
                builder.widget("a")
                builder.widget("b")

        Note:
            The ``col_weights`` and ``row_weights`` keyword arguments are
            deprecated in 0.4.1. Pass single-column/row weights via
            ``col_weight(col, weight)`` / ``row_weight(row, weight)`` inside
            the grid block instead.
        """
        block = _Grid(
            cells={}, padx=padx, pady=pady,
            fill=fill, expand=expand, uniform=uniform,
        )
        if col_weights:
            warnings.warn(
                "col_weights=... is deprecated; use builder.col_weight(col, weight) inside the grid block. "
                "Plural bulk arguments will be removed in nextpytk 0.5.0.",
                DeprecationWarning,
                stacklevel=2,
            )
        if row_weights:
            warnings.warn(
                "row_weights=... is deprecated; use builder.row_weight(row, weight) inside the grid block. "
                "Plural bulk arguments will be removed in nextpytk 0.5.0.",
                DeprecationWarning,
                stacklevel=2,
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
        padx: int = _PAD,
        pady: int = _PAD,
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
