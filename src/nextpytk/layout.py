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
import tkinter.ttk as ttk
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
    padx: int | None = _PAD
    pady: int | None = _PAD
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
    padx: int | None = _PAD
    pady: int | None = _PAD


@dataclass
class _Grid:
    """Internal: grid-based block."""
    cells: dict[str, dict[str, Any]]  # name -> {row, column, sticky, ...}
    padx: int | None = _PAD
    pady: int | None = _PAD
    fill: FillLike = "x"
    expand: ExpandLike = False
    uniform: str = ""
    # columnconfigure / rowconfigure (applied to frame)
    col_weights: dict[int, int] = field(default_factory=dict)
    col_minsize: dict[int, int] = field(default_factory=dict)
    row_weights: dict[int, int] = field(default_factory=dict)
    row_minsize: dict[int, int] = field(default_factory=dict)
    # Optional explicit visual/tab order. If provided, <Key-Tab> and
    # <Shift-Key-Tab> events are intercepted to move focus in this order
    # within the grid frame. Used by cluster blocks.
    order: tuple[str, ...] = ()


@dataclass
class _Nested:
    """Internal: a named nested frame containing an independent Layout."""
    name: str
    layout: Layout
    side: SideLike = "top"
    fill: FillLike = "x"
    expand: ExpandLike = False
    padx: int | None = _PAD
    pady: int | None = _PAD


@dataclass
class _Cluster:
    """Internal: a cluster block that packs widgets without stretching widths."""
    widgets: list[str]
    gap: int
    side: SideLike = "top"
    fill: FillLike = "x"
    expand: ExpandLike = False
    padx: int | None = _PAD
    pady: int | None = _PAD


@dataclass
class _Paired:
    """Internal: a paired block with two side-by-side widgets and optional scroll sync."""
    left: str
    right: str
    weight: tuple[int, ...] = (1, 1)
    sync_yscroll: bool = True
    side: SideLike = "top"
    fill: FillLike = "both"
    expand: ExpandLike = True
    padx: int | None = _PAD
    pady: int | None = _PAD


_Block = _Row | _Grid | _Paned | _Nested | _Cluster | _Paired


def _wire_cluster_tab_order(
    app: TkApp,
    frame: tk.Frame,
    order: tuple[str, ...],
) -> None:
    """Bind <Key-Tab> / <Shift-Key-Tab> on cluster children for visual tab order.

    Inserts a custom bindtag before the widget's class binding so the handler
    fires before ttk's built-in ``ttk::takefocus``. Text widgets are excluded
    because Tab is used for text input.
    """
    n = len(order)
    if n <= 1:
        return

    # Clean up stale bindtags for this frame before wiring the current order.
    prefix = f"ClusterTab{str(frame).replace('.', '_')}_"
    for name in order:
        w = app.widget(name)
        if w is None:
            continue
        tags = list(w.bindtags())
        for tag in list(tags):
            if tag.startswith(prefix):
                tags.remove(tag)
                frame.bind_class(tag, "<Key-Tab>", "")
                frame.bind_class(tag, "<Shift-Key-Tab>", "")
        w.bindtags(tags)

    for i, name in enumerate(order):
        w = app.widget(name)
        if w is None:
            continue
        # Text and Entry widgets use Tab for text input; skip them.
        if isinstance(w, (tk.Text, tk.Entry)):
            continue

        # Each widget gets its own bindtag so handlers don't accumulate
        # across widgets.
        tag = f"{prefix}{name}"

        # Tab: move to next in order, wrapping to the first item at the end.
        next_w = app.widget(order[(i + 1) % n])
        if next_w is not None:
            frame.bind_class(
                tag, "<Key-Tab>",
                lambda e, nw=next_w: _focus_and_break(nw, e),
            )
        # Shift-Tab: move to previous, wrapping to the last item at the start.
        prev_w = app.widget(order[(i - 1) % n])
        if prev_w is not None:
            frame.bind_class(
                tag, "<Shift-Key-Tab>",
                lambda e, pw=prev_w: _focus_and_break(pw, e),
            )

        # Insert the custom tag right after the widget's own tag so it
        # fires before the class binding (TButton, TEntry, etc.).
        tags = list(w.bindtags())
        if tag not in tags:
            tags.insert(1, tag)
            w.bindtags(tags)


def _focus_and_break(target: tk.Widget, event: tk.Event[tk.Misc]) -> str:
    """Focus *target* and stop event propagation."""
    try:
        target.focus_set()
    except tk.TclError:
        pass
    return "break"


def _cluster_rows(widgets: list[str], widths: list[int], gap_px: int, avail: int) -> list[list[str]]:
    """Group widget names into rows that fit in ``avail`` pixels.

    Each widget keeps its own width; a new row is started when the next
    widget plus gap would exceed the available width. At least one widget is
    always placed per row.
    """
    n = len(widgets)
    if n == 0:
        return []
    rows: list[list[str]] = []
    current: list[str] = [widgets[0]]
    used = widths[0]
    for i in range(1, n):
        needed = widths[i] + gap_px
        if used + needed <= avail:
            current.append(widgets[i])
            used += needed
        else:
            rows.append(current)
            current = [widgets[i]]
            used = widths[i]
    rows.append(current)
    return rows


def _place_cluster(app: TkApp, frame: tk.Frame, block: _Cluster) -> None:
    """Place cluster widgets without stretching, using absolute positioning.

    Uses ``place`` so widgets can be positioned inside *frame* regardless of
    their Tk window-tree parent.  Row heights and the overall frame height are
    computed from ``winfo_reqheight`` / ``winfo_reqwidth``.
    """
    gap_px = _t.SPACE[block.gap]
    padx = block.padx if block.padx is not None else 0
    pady = block.pady if block.pady is not None else 0

    # Collect widget info: (name, widget, reqwidth, reqheight)
    items: list[tuple[str, tk.Widget, int, int]] = []
    for name in block.widgets:
        tk_w = app._tk_widgets.get(name)
        if tk_w is None:
            continue
        try:
            rw = max(1, tk_w.winfo_reqwidth())
            rh = max(1, tk_w.winfo_reqheight())
        except tk.TclError:
            rw, rh = 1, 1
        items.append((name, tk_w, rw, rh))

    if not items:
        return

    # Forget any previous placement so we can re-place cleanly.
    for _, tk_w, _, _ in items:
        tk_w.place_forget()

    names = [it[0] for it in items]
    widths = [it[2] for it in items]

    try:
        avail = max(1, frame.winfo_width() - 2 * padx)
    except tk.TclError:
        avail = 1

    rows = _cluster_rows(names, widths, gap_px, avail)

    # Place each widget row by row.  Widgets keep their own height and
    # are vertically centered within the row so that tall widgets (e.g. an
    # entry) and short widgets (e.g. a button) align on their midline.
    y = pady
    ordered_names: list[str] = []
    for row_names in rows:
        row_height = max(
            (it[3] for it in items if it[0] in row_names),
            default=1,
        )
        x = padx
        for j, name in enumerate(row_names):
            item = next(it for it in items if it[0] == name)
            tk_w = item[1]
            w = item[2]
            h = item[3]
            is_last = j == len(row_names) - 1
            cy = y + (row_height - h) // 2
            tk_w.place(in_=frame, x=x, y=cy, width=w, height=h, anchor="nw")
            x += w + (0 if is_last else gap_px)
            ordered_names.append(name)
        y += row_height + gap_px

    # Set the cluster frame height explicitly; place does not propagate size.
    total_height = y - gap_px + pady
    frame.pack_propagate(False)
    frame.configure(height=total_height)

    _wire_cluster_tab_order(app, frame, tuple(ordered_names))


def _place_paired(app: TkApp, frame: tk.Frame, block: _Paired) -> None:
    """Grid two widgets side-by-side in ``frame`` and wire y-scroll sync.

    Both children are gridded sticky ``nsew`` so they share the full frame
    area according to the configured column weights.  When
    ``sync_yscroll=True`` and both registered widgets expose a real
    ``tk.Text`` (via ``app._text_inner``), their ``yscrollcommand`` chains are
    linked so scrolling either text moves the other.
    """
    left = app._tk_widgets.get(block.left)
    right = app._tk_widgets.get(block.right)
    if left is None or right is None:
        return

    # Ensure any previous geometry is cleared before gridding.
    left.grid_forget()
    right.grid_forget()

    left.grid(in_=frame, row=0, column=0, sticky="nsew", padx=(0, _t.SPACE[1] // 2))
    right.grid(in_=frame, row=0, column=1, sticky="nsew", padx=(_t.SPACE[1] // 2, 0))

    if not block.sync_yscroll:
        return

    text_a = app._text_inner.get(block.left)
    text_b = app._text_inner.get(block.right)
    if text_a is None or text_b is None:
        return

    # If the widgets already declared reciprocal sync_yscroll_with, the
    # app-level wiring in ``_wire_text_scroll_sync`` already handles bi-
    # directional movement and scrollbar updates.  Avoid installing a second,
    # conflicting layer that can create feedback loops or mask scrollbar events.
    if app._text_scroll_sync.get(block.left) == block.right:
        return

    sb_a = app._text_scrollbars.get(block.left)
    sb_b = app._text_scrollbars.get(block.right)

    def _sync_from_a(
        *args: Any,
        source: tk.Text = text_a,
        target: tk.Text = text_b,
        sb: ttk.Scrollbar | None = sb_a,
    ) -> None:
        target.yview_moveto(source.yview()[0])
        if sb is not None:
            sb.set(*args)

    def _sync_from_b(
        *args: Any,
        source: tk.Text = text_b,
        target: tk.Text = text_a,
        sb: ttk.Scrollbar | None = sb_b,
    ) -> None:
        target.yview_moveto(source.yview()[0])
        if sb is not None:
            sb.set(*args)

    text_a.configure(yscrollcommand=_sync_from_a)
    text_b.configure(yscrollcommand=_sync_from_b)


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


# ── Public API ──

def _pack_section_frame(parent: tk.Misc, block: _Row) -> tk.Frame:
    """Pack a section frame, optionally enforcing ``block.minsize``."""
    pack_kw: dict[str, Any] = {
        "side": "top", "fill": block.fill, "expand": block.expand,
        "padx": block.padx or 0, "pady": block.pady or 0,
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

    Args:
        spacing: Default padding for every block, expressed as a design token
            key from ``nextpytk.tokens.SPACE``. This sets the per-Layout
            ``padx``/``pady`` default used by ``section()``, ``grid()`` and
            ``paned()`` when those methods are not given explicit values.
            Default is ``1`` (``SPACE[1] == 4px``). Pass ``spacing=2`` to
            open the standard 8px gap, etc.
        padx, pady: Direct pixel overrides. If either is provided, it takes
            precedence over the value derived from ``spacing``.
    """

    padx: int | None = None
    pady: int | None = None
    spacing: int = 1

    _blocks: list[_Block] = field(default_factory=list)

    # Sentinel names used by chrome helpers; they are never registered as
    # real widgets, so they cannot collide with user widget names.
    _HEADER = "__kizashi_header__"
    _STATUS = "__kizashi_status__"

    def __post_init__(self) -> None:
        token = _t.SPACE.get(self.spacing)
        if token is None:
            valid = ", ".join(str(k) for k in sorted(_t.SPACE.keys()))
            raise ValueError(
                f"Layout spacing={self.spacing!r} is not a valid SPACE token; "
                f"choose from {valid}"
            )
        if self.padx is None:
            object.__setattr__(self, "padx", token)
        if self.pady is None:
            object.__setattr__(self, "pady", token)

    # ── section (pack) ──

    def section(
        self,
        *widgets: str,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
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
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
            minsize=minsize,
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
        padx: int | None = None,
        pady: int | None = None,
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
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
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
        padx: int | None = None,
        pady: int | None = None,
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
            cells={},
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
            fill=fill, expand=expand, uniform=uniform,
        )
        self._blocks.append(block)
        return _GridBuilder(self, block)

    # ── apply (called by TkApp.run) ──

    def widget_names(self) -> set[str]:
        """Return all widget names referenced by this layout and nested layouts."""
        out: set[str] = set()
        for block in self._blocks:
            if isinstance(block, _Row | _Cluster):
                out.update(block.widgets)
            elif isinstance(block, _Paned):
                out.add(block.name)
            elif isinstance(block, _Grid):
                out.update(block.cells.keys())
            elif isinstance(block, _Paired):
                out.update((block.left, block.right))
            elif isinstance(block, _Nested):
                out.update(block.layout.widget_names())
        return out

    def cluster(
        self,
        *widgets: str,
        gap: int | None = None,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Pack widgets in a wrapping-flow Cluster without stretching them.

        Widgets are arranged left-to-right, top-to-bottom, wrapping to a new
        row whenever the next widget would not fit in the remaining frame
        width. Each widget keeps the width implied by its content or
        ``width=`` (e.g. an ``entry(width=30)`` stays wider than a short
        button) rather than being stretched to fill a column.

        ``gap`` is a key from ``nextpytk.tokens.SPACE`` and controls both the
        horizontal gap between items and the vertical gap between rows. When
        omitted it inherits the Layout's ``spacing`` setting.

        Example::

            Layout().cluster("tag1", "tag2", "tag3", "tag4")
        """
        effective_gap = gap if gap is not None else self.spacing
        if effective_gap not in _t.SPACE:
            valid = ", ".join(str(k) for k in sorted(_t.SPACE.keys()))
            raise ValueError(
                f"Cluster gap={effective_gap!r} is not a valid SPACE token; choose from {valid}"
            )
        ws = list(widgets)
        self._blocks.append(_Cluster(
            widgets=ws,
            gap=effective_gap,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
        ))
        return self

    def paired(
        self,
        left: str,
        right: str,
        *,
        weight: tuple[int, int] | list[int] = (1, 1),
        sync_yscroll: bool = True,
        side: SideLike = "top",
        fill: FillLike = "both",
        expand: ExpandLike = True,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Place two widgets side-by-side in a single frame with optional scroll sync.

        Designed for diff / compare views (e.g. tkmerge left/right file panes).
        Both widgets share the available width according to ``weight`` and fill
        the frame. When ``sync_yscroll=True`` the vertical scroll position of
        one widget follows the other (requires scrollable widgets such as
        ``@app.text``).

        Example::

            app.text("left", readonly=True, sync_yscroll_with="right")
            app.text("right", sync_yscroll_with="left")
            Layout().paired("left", "right", weight=(1, 1), sync_yscroll=True)

        Scroll sync is a layout-level hint; each text widget should also
        declare the reciprocal ``sync_yscroll_with`` option so the underlying
        ``yscrollcommand`` chain is already wired by ``TkApp._build_widgets``.
        This method additionally ensures the pair share a common frame and
        the same visual height.
        """
        self._blocks.append(_Paired(
            left=left,
            right=right,
            weight=tuple(weight),  # type: ignore[arg-type]
            sync_yscroll=sync_yscroll,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
        ))
        return self

    def frame(
        self,
        name: str,
        layout: Layout,
        *,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Add a named nested frame that contains its own independent ``Layout``.

        The nested layout is mounted inside a new Frame which is packed into the
        parent layout. Widgets inside ``layout`` must still be registered in the
        same ``TkApp``; they are simply grouped visually.

        Example::

            inner = Layout().section("a").section("b")
            Layout().section("title").frame("group", inner).section("ok")
        """
        self._blocks.append(_Nested(
            name=name,
            layout=layout,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
        ))
        return self

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
                    padx=block.padx or 0, pady=block.pady or 0,
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
                    padx=block.padx or 0, pady=block.pady or 0,
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
            elif isinstance(block, _Cluster):
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
                for name in block.widgets:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                # Defer packing until children exist; store the cluster block
                # on the frame for the Configure handler to re-layout.
                frame._cluster_block = block  # type: ignore[attr-defined]
                grid_jobs.append((frame, _Grid(cells={}, padx=0, pady=0)))
            elif isinstance(block, _Paired):
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
                # Two-column grid: left and right share the width by weight.
                frame.columnconfigure(0, weight=block.weight[0])
                frame.columnconfigure(1, weight=block.weight[1])
                frame.rowconfigure(0, weight=1)
                for name in (block.left, block.right):
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                # Store the pair metadata for pack_children_for.
                frame._paired_block = block  # type: ignore[attr-defined]
                grid_jobs.append((frame, _Grid(cells={}, padx=0, pady=0)))
            elif isinstance(block, _Nested):
                # Mount a new Frame, then recursively mount the nested Layout
                # inside it. The nested Layout manages its own frame hierarchy.
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=t.BG, bd=0, highlightthickness=0)
                nested_row_jobs, nested_grid_jobs = block.layout.mount_frames_into(
                    app, frame, allowed_widgets=allowed_widgets
                )
                row_jobs.extend(nested_row_jobs)
                grid_jobs.extend(nested_grid_jobs)
                # Register the nested frame so the parent can place it inside a
                # grid cell, and so it is not repacked as a regular child.
                app._tk_widgets[block.name] = frame
                app._widget_masters[block.name] = frame

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
                        padx=(0, 0 if is_last else row.padx or 0), pady=0,
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
            # Cluster blocks are placed without stretching widths, not gridded.
            block = getattr(_frame, "_cluster_block", None)
            if isinstance(block, _Cluster):
                _place_cluster(app, _frame, block)
                # Recompute row wrapping whenever the cluster frame is resized.
                _frame.bind(
                    "<Configure>",
                    lambda e, a=app, f=_frame, b=block: (
                        _place_cluster(a, f, b) if e.widget == f else None
                    ),
                    add=True,
                )
                continue

            # Paired blocks: two-column grid with optional y-scroll sync.
            pblock = getattr(_frame, "_paired_block", None)
            if isinstance(pblock, _Paired):
                _place_paired(app, _frame, pblock)
                continue

            for name, opts in gb.cells.items():
                tk_w = app._tk_widgets.get(name)
                if tk_w is None:
                    continue
                grid_opts = {k: v for k, v in opts.items()
                             if k in ("row", "column", "sticky", "padx", "pady",
                                      "columnspan", "rowspan")}
                # Explicitly place the cell widget inside the grid frame.
                # Nested frames are packed into the parent body by
                # ``mount_frames_into``; without ``in_`` the geometry
                # manager would try to grid them in the wrong parent and
                # conflict with packed siblings.
                grid_opts["in_"] = _frame
                tk_w.grid(**grid_opts)
            # Wire cluster tab order via <Key-Tab> / <Shift-Key-Tab> bindings.
            # Tk has no native API to reorder focus traversal, so we intercept
            # the events and move focus in the visual row-major order.
            if gb.order:
                _wire_cluster_tab_order(app, _frame, gb.order)

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
        padx: int | None = None,
        pady: int | None = None,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> _GridBuilder:
        """Place a widget at the current cursor position, then advance column.

        ``colspan`` overrides any previously-set colspan (via ``.span(...)``).
        """
        cs = colspan if colspan is not None else self._colspan
        opts: dict[str, Any] = {
            "row": self._row, "column": self._col,
            "sticky": sticky,
            "padx": padx if padx is not None else self._layout.padx,
            "pady": pady if pady is not None else self._layout.pady,
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
        padx: int | None = None,
        pady: int | None = None,
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
        padx: int | None = None,
        pady: int | None = None,
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

    def frame(
        self,
        name: str,
        layout: Layout,
        *,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> None:
        """Add a named nested frame containing an independent ``Layout``."""
        self._layout.frame(
            name,
            layout,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        )

    def cluster(
        self,
        *widgets: str,
        gap: int | None = None,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> None:
        """Add a cluster block to the layout (see ``Layout.cluster``)."""
        self._layout.cluster(
            *widgets,
            gap=gap,
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
        padx: int | None = None,
        pady: int | None = None,
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
            cells={},
            padx=padx if padx is not None else self._layout.padx,
            pady=pady if pady is not None else self._layout.pady,
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
        padx: int | None = None,
        pady: int | None = None,
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
