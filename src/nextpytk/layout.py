"""IoC container for layout: inject frame/pack/grid structure into TkApp.

Fluent DSL for arranging widgets registered in TkApp.

Two modes:
- ``.section(...)`` — pack-based section (one Frame, widgets pack inside)
- ``.grid()`` → ``_GridBuilder`` — grid-based placement with ``cell`` / ``end_grid``

Both are chainable: ``Layout().section("a").grid().cell("b").end_grid().section("c")``.

``GridBuilder.widget()`` is deprecated (0.4.13); use ``GridBuilder.cell()``
instead.

Types from ``nextpytk.types`` provide IDE autocomplete for options.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nextpytk import tokens as _t
from nextpytk.types import (
    AnchorLike,
    ExpandLike,
    FillLike,
    Flex,
    OrientLike,
    SideLike,
)

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
    # Side used to pack children *inside* the section frame. ``section()``
    # sets this to "left" when more than one widget is given (children laid
    # out side-by-side), keeping ``side`` as the frame's own placement side
    # in the parent. They diverge only in that multi-widget case.
    child_side: SideLike = "top"
    fill: FillLike = "x"
    expand: ExpandLike = False
    padx: int | None = _PAD
    pady: int | None = _PAD
    minsize: int | None = None
    anchor: AnchorLike | None = None
    # Optional stable name for the section frame, used to address it with
    # ``app.hide_section()`` / ``app.show_section()``. When omitted, the
    # frame is registered as "<first widget>_section".
    name: str | None = None
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
    # Raw tkinter widgets placed via cell_raw().  Each entry is
    # (widget, {row, column, sticky, padx, pady, columnspan, rowspan}).
    raw_cells: list[tuple[tk.Widget, dict[str, Any]]] = field(default_factory=list)


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
class _Target:
    """Internal: a reserved swap region whose contents can be swapped at runtime.

    Mirrors HTMX ``hx-target``: the region is a persistent frame, and its
    inner variants are mounted as hidden sub-frames that ``app.swap()``
    shows/hides.
    """
    name: str
    side: SideLike = "top"
    fill: FillLike = "both"
    expand: ExpandLike = True
    padx: int | None = _PAD
    pady: int | None = _PAD


@dataclass
class _Wrap:
    """Internal: a wrapping-flow block (Flutter ``Wrap`` analog).

    Widgets are laid left-to-right and wrap onto a new row when they no
    longer fit in the available frame width. Each widget keeps the width
    implied by its content or ``width=`` unless it is wrapped in ``Flex``,
    in which case it absorbs a share of leftover horizontal space.
    """
    widgets: list[str | Flex]
    gap: int
    gapx: int | None = None  # horizontal (in-row) gap; falls back to gap
    gapy: int | None = None  # vertical (row-to-row) gap; falls back to gap
    side: SideLike = "top"
    fill: FillLike = "x"
    expand: ExpandLike = False
    padx: int | None = _PAD
    pady: int | None = _PAD


# Alias kept for backward compatibility with the pre-0.5 name.
_Cluster = _Wrap


@dataclass
class Constraints:
    """Available space handed to a ``FlowDelegate``.

    Mirrors Flutter's ``BoxConstraints``: the delegate decides how to split
    the given ``width``/``height`` among its children.

    ``sizes`` maps each child widget name to its natural (requested) size
    ``(reqwidth, reqheight)``, so a delegate can size cells to fit content
    (e.g. a button whose label is 67px tall) instead of clipping it.
    """

    width: int
    height: int
    min_width: int = 0
    max_width: int = 100_000
    min_height: int = 0
    max_height: int = 100_000
    sizes: dict[str, tuple[int, int]] = field(default_factory=dict)


class FlowDelegate(ABC):
    """Custom flow layout algorithm (Flutter ``FlowDelegate`` analog).

    Subclass and override :meth:`compute_positions` to position children
    within the available space. ``place`` is used underneath, so any
    (x, y, width, height) you return is honoured without fighting the other
    geometry managers.

    Example::

        class GridDelegate(FlowDelegate):
            def __init__(self, cols: int, gap: int = 1):
                self.cols = cols
                self.gap = gap

            def compute_positions(self, children, constraints):
                gap = _t.SPACE[self.gap]
                cell = (constraints.width - gap * (self.cols - 1)) // self.cols
                return {
                    name: (i % self.cols * (cell + gap),
                           i // self.cols * (cell + gap),
                           cell, cell)
                    for i, name in enumerate(children)
                }
    """

    @abstractmethod
    def compute_positions(
        self,
        children: list[str],
        constraints: Constraints,
    ) -> dict[str, tuple[int, int, int, int]]:
        """Return ``{widget_name: (x, y, width, height)}`` for each child."""
        raise NotImplementedError

    def compute_height(
        self,
        children: list[str],
        constraints: Constraints,
    ) -> int:
        """Requested height for the flow frame. Defaults to available height."""
        return constraints.height


@dataclass
class _Flow:
    """Internal: a flow block whose positions come from a ``FlowDelegate``."""
    widgets: list[str]
    delegate: FlowDelegate
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
    line_numbers: bool = False
    side: SideLike = "top"
    fill: FillLike = "both"
    expand: ExpandLike = True
    padx: int | None = _PAD
    pady: int | None = _PAD


_Block = _Row | _Grid | _Paned | _Nested | _Cluster | _Paired | _Target | _Flow



def _tab_target(app: TkApp, name: str) -> tk.Widget | None:
    """Return the widget that actually receives keyboard focus for *name*.

    A registered ``text`` is wrapped in a container; the real ``tk.Text``
    (in ``app._text_inner``) is the focusable part. Everything else focuses
    through ``app._tk_widgets``.
    """
    if name in app._text_inner:
        return app._text_inner.get(name)
    return app._tk_widgets.get(name)


def _place_position(app: TkApp, w: tk.Widget) -> tuple[int, int]:
    """Return the absolute (x, y) position of *w* on screen.

    Uses ``winfo_rootx``/``winfo_rooty`` so widgets in different wrap/flow
    frames (each of which has its own local ``place`` coordinates) compare
    correctly against each other.
    """
    try:
        return (int(w.winfo_rooty()), int(w.winfo_rootx()))
    except (tk.TclError, TypeError, ValueError):
        return (10_000_000, 10_000_000)


def _focusable_order(app: TkApp) -> list[str]:
    """Focusable widget names ordered by their visual (y, x) placement.

    Tk's native ``tk_focusNext``/``tk_focusPrev`` follow window stacking
    order, which is unreliable for ``place``-managed children (it can loop
    inside a group). We instead sort the currently-placed, focusable widgets
    by their ``place`` (y, x) coordinates so Tab traversal matches the visual
    row-major order across wrap/flow blocks.

    Only widgets currently managed by ``place`` are considered: a wrap/flow
    child that was not placed (e.g. registered but omitted from the layout)
    is invisible and must not be a Tab destination.
    """
    out: list[str] = []
    for name in app._tk_widgets:
        w = app._tk_widgets[name]
        if not w.winfo_exists() or w.winfo_manager() != "place":
            continue
        try:
            tf = w.cget("takefocus")
        except tk.TclError:
            continue
        if tf is False or tf == 0 or tf == "0" or tf == "":
            continue
        out.append(name)
    # Multiline Text widgets take focus via their inner tk.Text, which is
    # placed inside the container.
    for name in app._text_inner:
        inner = app._text_inner[name]
        if inner.winfo_exists() and inner.winfo_manager() == "place" and name not in out:
            out.append(name)
    # Order by (y, x) so traversal follows the visual layout.
    out.sort(
        key=lambda nm: _place_position(app, _tab_target(app, nm) or app._tk_widgets[nm])
    )
    return out


def _focus_exit(app: TkApp, order: tuple[str, ...], *, forward: bool) -> tk.Widget | None:
    """Focusable widget just outside *order* (a group), in visual (y, x) order.

    Scans past every member of the current group so focus never loops back
    inside it. ``forward`` finds the first focusable widget placed after the
    group's last member; ``backward`` finds the one before the group's first.
    When the group is at the very end/start of the window, focus wraps around
    to the first/last focusable widget (like native Tab traversal).
    """
    all_names = _focusable_order(app)
    group = set(order)
    members = [n for n in all_names if n in group]
    if not members:
        return None
    gi = all_names.index(members[-1]) if forward else all_names.index(members[0])
    # Scan past the whole group, then take the first non-group member.
    step = 1 if forward else -1
    for offset in range(1, len(all_names) + 1):
        idx = (gi + offset * step) % len(all_names)
        name = all_names[idx]
        if name not in group:
            return _tab_target(app, name)
    return None


def _wire_tab_order(
    app: TkApp,
    frame: tk.Frame,
    order: tuple[str, ...],
) -> None:
    """Bind <Key-Tab> / <Shift-Key-Tab> on layout children for visual tab order.

    Because ``wrap`` and ``flow`` position children with ``place`` (not
    ``pack``/``grid``), Tk's native Tab traversal — which is based on the order
    children were added to a managed master — does not reflect the visual
    row-major order after reflow. So we intercept ``<Key-Tab>`` /
    ``<Shift-Key-Tab>`` and move focus in the computed visual order instead.

    Inserts a custom bindtag before the widget's class binding so the handler
    fires before ttk's built-in ``ttk::takefocus`` and returns ``break``.

    By default every registered child participates in the cycle — including
    ``Text`` — so Tab moves focus (it does not insert a tab character). Apps
    that want Tab to insert a tab inside a ``Text`` can opt in by disabling
    this for that widget.

    The group is *not* closed: on the last child, Tab moves to the next
    focusable widget *outside* the group (``_focus_exit``), and the first
    child's Shift-Tab to the previous one outside it. This escapes the group
    deterministically instead of relying on Tk's stacking-order
    ``tk_focusNext``, which can loop inside a ``place`` group.
    """
    n = len(order)
    if n <= 1:
        return

    # Clean up stale bindtags for this frame before wiring the current order.
    prefix = f"TabOrder{str(frame).replace('.', '_')}_"
    for name in order:
        w = _tab_target(app, name)
        if w is None:
            continue
        tags = list(w.bindtags())
        for tag in list(tags):
            if tag.startswith(prefix):
                tags.remove(tag)
                frame.bind_class(tag, "<Key-Tab>", "")
                frame.bind_class(tag, "<Shift-Key-Tab>", "")
        w.bindtags(tags)

    m = n
    for i, name in enumerate(order):
        w = _tab_target(app, name)
        if w is None:
            continue
        tag = f"{prefix}{name}"

        # Tab: move to the next item, or out of the group at the last one.
        if i + 1 < m:
            next_w = _tab_target(app, order[i + 1])
            handler = lambda e, nw=next_w: _focus_and_break(nw, e)  # noqa: E731
        else:
            handler = lambda e, a=app, o=order: _focus_exit_break(a, o, True, e)  # noqa: E731
        frame.bind_class(tag, "<Key-Tab>", handler)

        # Shift-Tab: move to the previous item, or out at the first one.
        if i - 1 >= 0:
            prev_w = _tab_target(app, order[i - 1])
            handler = lambda e, pw=prev_w: _focus_and_break(pw, e)  # noqa: E731
        else:
            handler = lambda e, a=app, o=order: _focus_exit_break(a, o, False, e)  # noqa: E731
        frame.bind_class(tag, "<Shift-Key-Tab>", handler)

        # Insert the custom tag right after the widget's own tag so it
        # fires before the class binding (TButton, TEntry, etc.).
        tags = list(w.bindtags())
        if tag not in tags:
            tags.insert(1, tag)
            w.bindtags(tags)


def _focus_and_break(target: tk.Widget | None, event: tk.Event[tk.Misc]) -> str:
    """Focus *target* (if any) and stop event propagation."""
    if target is None:
        return "break"
    try:
        target.focus_set()
    except tk.TclError:
        pass
    return "break"


def _focus_exit_break(
    app: TkApp,
    order: tuple[str, ...],
    forward: bool,
    event: tk.Event[tk.Misc] | None = None,
) -> str:
    """Focus the widget just outside *order*, then stop propagation."""
    target = _focus_exit(app, order, forward=forward)
    if target is not None:
        try:
            target.focus_set()
        except tk.TclError:
            pass
    return "break"


def _validate_gap(value: int, label: str) -> None:
    """Raise if *value* is not a valid SPACE token key."""
    if value not in _t.SPACE:
        valid = ", ".join(str(k) for k in sorted(_t.SPACE.keys()))
        raise ValueError(
            f"Cluster {label}={value!r} is not a valid SPACE token; choose from {valid}"
        )


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
    """Place wrap widgets without stretching, using absolute positioning.

    Uses ``place`` so widgets can be positioned inside *frame* regardless of
    their Tk window-tree parent.  Row heights and the overall frame height are
    computed from ``winfo_reqheight`` / ``winfo_reqwidth``.  Items wrapped in
    ``Flex`` absorb leftover horizontal space within their row, proportional
    to their flex factor (Flutter ``Expanded`` analog).
    """
    gapx_px = _t.SPACE[block.gapx if block.gapx is not None else block.gap]
    gapy_px = _t.SPACE[block.gapy if block.gapy is not None else block.gap]
    padx = block.padx if block.padx is not None else 0
    pady = block.pady if block.pady is not None else 0

    # Resolve each entry to (name, flex_factor_or_None, widget, reqw, reqh).
    items: list[tuple[str, int | None, tk.Widget, int, int]] = []
    for entry in block.widgets:
        if isinstance(entry, Flex):
            name = entry.widget
            flex = entry.flex
        else:
            name = entry
            flex = None
        tk_w = app._tk_widgets.get(name)
        if tk_w is None:
            continue
        try:
            rw = max(1, tk_w.winfo_reqwidth())
            rh = max(1, tk_w.winfo_reqheight())
        except tk.TclError:
            rw, rh = 1, 1
        items.append((name, flex, tk_w, rw, rh))

    if not items:
        return

    # Forget any previous placement so we can re-place cleanly.
    for _, _, tk_w, _, _ in items:
        tk_w.place_forget()

    names = [it[0] for it in items]
    widths = [it[3] for it in items]

    try:
        avail = max(1, frame.winfo_width() - 2 * padx)
    except tk.TclError:
        avail = 1

    rows = _cluster_rows(names, widths, gapx_px, avail)

    # Place each widget row by row.  Widgets keep their own height and
    # are vertically centered within the row so that tall widgets (e.g. an
    # entry) and short widgets (e.g. a button) align on their midline.
    y = pady
    ordered_names: list[str] = []
    for row_names in rows:
        row_items = [it for it in items if it[0] in row_names]
        row_height = max((it[4] for it in row_items), default=1)
        # Leftover space is shared among flex items in this row.
        used = sum(it[3] for it in row_items) + gapx_px * (len(row_items) - 1)
        leftover = max(0, avail - used)
        flex_items = [it for it in row_items if it[1] is not None]
        total_flex = sum((it[1] or 0) for it in flex_items)
        flex_extra: dict[str, int] = {}
        if total_flex > 0:
            for it in flex_items:
                flex_extra[it[0]] = leftover * (it[1] or 0) // total_flex
        x = padx
        for j, (name, flex, tk_w, rw, rh) in enumerate(row_items):
            w = rw + flex_extra.get(name, 0)
            h = rh
            is_last = j == len(row_items) - 1
            cy = y + (row_height - h) // 2
            tk_w.place(in_=frame, x=x, y=cy, width=w, height=h, anchor="nw")
            x += w + (0 if is_last else gapx_px)
            ordered_names.append(name)
        y += row_height + gapy_px

    # Set the wrap frame height explicitly; place does not propagate size.
    total_height = y - gapy_px + pady
    frame.pack_propagate(False)
    frame.configure(height=total_height)

    _wire_tab_order(app, frame, tuple(ordered_names))


def _place_flow(app: TkApp, frame: tk.Frame, block: _Flow) -> None:
    """Place widgets using a custom ``FlowDelegate`` algorithm.

    Positions and sizes come from the delegate's ``compute_positions``; the
    frame height comes from ``compute_height``. On resize the positions are
    recomputed so the flow stays responsive.
    """
    padx = block.padx if block.padx is not None else 0
    pady = block.pady if block.pady is not None else 0

    # Collect each child's natural (requested) size so the delegate can size
    # cells to fit content rather than clipping it.
    sizes: dict[str, tuple[int, int]] = {}
    for name in block.widgets:
        tk_w = app._tk_widgets.get(name)
        if tk_w is None:
            continue
        try:
            sizes[name] = (max(1, tk_w.winfo_reqwidth()), max(1, tk_w.winfo_reqheight()))
        except tk.TclError:
            sizes[name] = (1, 1)

    # Forget previous placements.
    for name in block.widgets:
        tk_w = app._tk_widgets.get(name)
        if tk_w is not None:
            tk_w.place_forget()

    try:
        avail_w = max(1, frame.winfo_width() - 2 * padx)
        avail_h = max(1, frame.winfo_height() - 2 * pady)
    except tk.TclError:
        avail_w, avail_h = 100, 100

    constraints = Constraints(width=avail_w, height=avail_h, sizes=sizes)
    positions = block.delegate.compute_positions(block.widgets, constraints)

    # Place children exactly where the delegate decided. The delegate is
    # responsible for sizing cells to fit content — it can read each child's
    # natural size from ``constraints.sizes``. Clamping sizes here would
    # misalign rows (a larger height at a position computed for a smaller
    # cell), so we honor the delegate's geometry as-is.
    placed_height = 0
    for name, (x, y, w, h) in positions.items():
        tk_w = app._tk_widgets.get(name)
        if tk_w is None:
            continue
        tk_w.place(in_=frame, x=x + padx, y=y + pady, width=w, height=h, anchor="nw")
        placed_height = max(placed_height, y + h)

    # Frame height covers the tallest placed cell; fall back to the delegate's
    # own estimate when no cell extends past it.
    delegate_height = block.delegate.compute_height(block.widgets, constraints)
    height = max(delegate_height, placed_height) + 2 * pady
    frame.pack_propagate(False)
    frame.configure(height=height)
    _wire_tab_order(app, frame, tuple(block.widgets))


def _place_paired(app: TkApp, frame: tk.Frame, block: _Paired) -> None:
    """Grid two widgets side-by-side in ``frame`` and wire y-scroll sync.

    Both children are gridded sticky ``nsew`` so they share the full frame
    area according to the configured column weights.  When
    ``sync_yscroll=True`` and both registered widgets expose a real
    ``tk.Text`` (via ``app._text_inner``), their ``yscrollcommand`` chains are
    linked so scrolling either text moves the other.

    When ``line_numbers=True``, a read-only line-number gutter is added to each
    side and both panes + both gutters share a single vertical scrollbar, so
    the gutters stay in lock-step with the content. This is the only reliable
    way to keep gutters synchronized (per-widget ``yview_moveto`` chaining
    drifts), and it works even for ``disabled`` gutter widgets.
    """
    left = app._tk_widgets.get(block.left)
    right = app._tk_widgets.get(block.right)
    if left is None or right is None:
        return

    # Ensure any previous geometry is cleared before gridding.
    left.grid_forget()
    right.grid_forget()

    text_a = app._text_inner.get(block.left)
    text_b = app._text_inner.get(block.right)

    if block.line_numbers:
        _place_paired_with_gutters(app, frame, block, left, right, text_a, text_b)
        return

    left.grid(in_=frame, row=0, column=0, sticky="nsew", padx=(0, _t.SPACE[1] // 2))
    right.grid(in_=frame, row=0, column=1, sticky="nsew", padx=(_t.SPACE[1] // 2, 0))

    if not block.sync_yscroll:
        return

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


def _place_paired_with_gutters(
    app: TkApp,
    frame: tk.Frame,
    block: _Paired,
    left: tk.Widget,
    right: tk.Widget,
    text_a: tk.Text | None,
    text_b: tk.Text | None,
) -> None:
    """Place paired panes with read-only line-number gutters.

    Layout::

        [gutter_a] [pane_a] [gutter_b] [pane_b] [shared Vscroll]

    All four widgets share ONE vertical scrollbar. Each widget's
    ``yscrollcommand`` is chained so that whenever any widget scrolls (mouse
    wheel, arrow keys, drag, or programmatic ``yview_moveto``), the other
    three follow to the same position, and the shared scrollbar's slider is
    updated. The shared scrollbar's ``command`` drives all four too. This keeps
    the ``disabled`` gutters in lock-step with the content (no drift).
    """
    # Gutter helpers (created once; stored on the frame for re-run safety).
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    gutter_b = getattr(frame, "_paired_gutter_b", None)
    shared_sb = getattr(frame, "_paired_shared_scroll", None)

    if shared_sb is None:
        shared_sb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        shared_sb.grid(row=0, column=4, sticky="ns")
        frame._paired_shared_scroll = shared_sb  # type: ignore[attr-defined]

    if gutter_a is None:
        gutter_a = _make_gutter(frame, f"{block.left}_gutter")
        gutter_a.grid(row=0, column=0, sticky="nsew")
        frame._paired_gutter_a = gutter_a  # type: ignore[attr-defined]
    if gutter_b is None:
        gutter_b = _make_gutter(frame, f"{block.right}_gutter")
        gutter_b.grid(row=0, column=2, sticky="nsew")
        frame._paired_gutter_b = gutter_b  # type: ignore[attr-defined]

    left.grid(in_=frame, row=0, column=1, sticky="nsew")
    right.grid(in_=frame, row=0, column=3, sticky="nsew")

    # Column weights: gutter cols fixed, pane cols follow block.weight.
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(2, weight=0)
    frame.columnconfigure(1, weight=block.weight[0])
    frame.columnconfigure(3, weight=block.weight[1])

    if text_a is None or text_b is None:
        return

    widgets = (text_a, text_b, gutter_a, gutter_b)
    pairs = ((gutter_a, text_a), (gutter_b, text_b))

    # Shared scrollbar command: scroll all four in one move.
    def _shared_cmd(*args: str) -> None:
        for w in widgets:
            try:
                w.yview(*args)
            except tk.TclError:
                pass

    shared_sb.configure(command=_shared_cmd)

    # Chain each widget's yscrollcommand so scrolling any one moves the rest.
    for source in widgets:
        source.configure(
            yscrollcommand=lambda *a, src=source, pr=pairs: _chain_yview(
                src, widgets, shared_sb, pr, *a
            )
        )

    # Hide the per-widget scrollbars that @app.text created so only the
    # shared one is visible.
    for name in (block.left, block.right):
        per_widget_sb = app._text_scrollbars.get(name)
        if per_widget_sb is not None:
            per_widget_sb.grid_remove()

    # Populate logical line numbers (also reconciles on every scroll so a
    # gutter always mirrors its pane's current line count).
    _reconcile_gutter(gutter_a, text_a)
    _reconcile_gutter(gutter_b, text_b)
    # Keep gutters in sync when content is replaced via app.text_set().
    app.on_text_set(block.left, lambda g=gutter_a, t=text_a: _reconcile_gutter(g, t))
    app.on_text_set(block.right, lambda g=gutter_b, t=text_b: _reconcile_gutter(g, t))
    # Keep the right gutter's line numbers in sync as the right pane edits.
    _bind_gutter_edit_sync(app, text_b, gutter_b)


def _logical_line_count(text: tk.Text) -> int:
    """Return the number of logical (non-wrapped) lines in *text*.

    ``index("end-1c")`` counts *display* lines: a long line that wraps to
    several rows inflates the count when ``wrap`` is ``word``/``char``. We
    count newline characters instead, which is wrap-independent. The last
    logical line may or may not carry a trailing newline (``text_set`` omits
    it; a hand-inserted buffer may keep it), so the count is adjusted by
    whether the content ends with a newline.
    """
    try:
        content = text.get("1.0", "end-1c")
    except tk.TclError:
        return 0
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def _reconcile_gutter(gutter: tk.Text, text: tk.Text) -> None:
    """Fill a gutter with logical line numbers, matching the text line count.

    If the text gained/lost rows (edit or programmatic ``text_set``), the
    gutter is rewritten so its scroll range matches the pane. Idempotent:
    rewriting only happens when the count differs.
    """
    # Re-entry guard: rewriting the gutter fires yscrollcommand on the shared
    # scrollbar (via update_idletasks below), which re-enters this function
    # through _chain_yview. Without a guard that recursion never terminates.
    if getattr(gutter, "_syncing_gutter", False):
        return
    n = _logical_line_count(text)
    gutter_lines = int(gutter.index("end-1c").split(".")[0])
    if gutter_lines == n:
        return
    lines = "\n".join(str(i) for i in range(1, n + 1))
    gutter._syncing_gutter = True  # type: ignore[attr-defined]
    try:
        gutter.configure(state="normal")
        gutter.delete("1.0", "end")
        gutter.insert("1.0", lines)
        gutter.configure(state="disabled")
        # Ensure the new content is reflected in the shared scrollbar range.
        gutter.update_idletasks()
    finally:
        gutter._syncing_gutter = False  # type: ignore[attr-defined]


def _chain_yview(
    source: tk.Text,
    widgets: tuple[tk.Text, ...],
    shared_sb: ttk.Scrollbar,
    gutter_pairs: tuple[tuple[tk.Text, tk.Text], ...],
    *args: str,
) -> None:
    """Move all widgets to ``source``'s current y-position; update the slider.

    Also reconciles each gutter with its pane's line count so gutters never
    drift out of sync with the content they annotate.
    """
    try:
        fraction = source.yview()[0]
    except tk.TclError:
        return
    for gutter, pane in gutter_pairs:
        _reconcile_gutter(gutter, pane)
    for w in widgets:
        if w is source:
            continue
        try:
            w.yview_moveto(fraction)
        except tk.TclError:
            pass
    try:
        shared_sb.set(*args)
    except tk.TclError:
        pass


def _make_gutter(parent: tk.Misc, name: str) -> tk.Text:
    """Create a read-only line-number gutter."""
    gutter = tk.Text(
        parent,
        width=5,
        height=1,
        name=name,
        bg=_t.SURFACE,
        fg=_t.TEXT_MUTED,
        font=_t.font("body"),
        relief="flat",
        bd=0,
        highlightthickness=0,
        wrap="none",
        cursor="arrow",
        state="disabled",
        takefocus=0,
    )
    return gutter


def _populate_gutters(gutter: tk.Text, text: tk.Text) -> None:
    """Fill a gutter with logical line numbers (1..n)."""
    if getattr(gutter, "_syncing_gutter", False):
        return
    n = _logical_line_count(text)
    lines = "\n".join(str(i) for i in range(1, n + 1))
    gutter._syncing_gutter = True  # type: ignore[attr-defined]
    try:
        gutter.configure(state="normal")
        gutter.delete("1.0", "end")
        gutter.insert("1.0", lines)
        gutter.configure(state="disabled")
        # Ensure the new content is reflected in the shared scrollbar range.
        gutter.update_idletasks()
    finally:
        gutter._syncing_gutter = False  # type: ignore[attr-defined]


def _bind_gutter_edit_sync(app: TkApp, text: tk.Text, gutter: tk.Text) -> None:
    """Re-sync a gutter when its pane text content changes."""
    def _on_key(_event: tk.Event[tk.Misc]) -> None:
        _populate_gutters(gutter, text)
    text.bind("<KeyRelease>", _on_key, add="+")


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
        "side": block.side, "fill": block.fill, "expand": block.expand,
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
        page_margin: The outer page margin (pixels) applied to the root's
            ``content_frame`` when the layout is run at a top level (the
            default Kizashi page pad, ``SPACE[6]`` / 24px). Set to 0 to make
            the layout hug the window edge. This only affects the outermost
            ``content_frame``; per-block ``padx``/``pady`` still apply.
    """

    padx: int | None = None
    pady: int | None = None
    spacing: int = 1
    page_margin: int | None = None

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
        name: str | None = None,
    ) -> Layout:
        """Add a pack-based section.

        One Frame is created; widgets are pack'ed inside it side-by-side.
        When a single widget is passed, fill/expand also apply to the child.

        ``minsize``: minimum pixels along the grow axis — height for
        ``fill=\"both\"`` / ``fill=\"y\"``, width for ``fill=\"x\"``.
        ``anchor``: where a non-filling section sits in the window.
        Defaults to ``\"w\"`` (left) for ``fill=\"none\"`` / ``\"y\"`` —
        pass ``anchor=\"center\"`` to center it.

        ``name``: an optional stable label for the section frame so it can be
        addressed with ``app.hide_section(name)`` / ``app.show_section(name)``.
        Only sections with an explicit ``name`` are addressable this way; the
        name must not collide with a widget name.
        """
        ws = list(widgets)
        # Children of a multi-widget section lay out side-by-side regardless
        # of where the section frame itself is packed (side= may be top,
        # bottom, left, or right). A single-widget section packs its child
        # with the frame's own placement side.
        child_side: SideLike = "left" if len(ws) > 1 else "top"
        self._blocks.append(_Row(
            widgets=ws, side=side, child_side=child_side, fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
            minsize=minsize,
            anchor=anchor,
            name=name,
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

    def target(
        self,
        name: str,
        *,
        side: SideLike = "top",
        fill: FillLike = "both",
        expand: ExpandLike = True,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Reserve a swap target: a region whose contents are swapped at runtime.

        Mirrors HTMX ``hx-target``: the region is a persistent frame, and
        variant layouts (declared with ``@app.swap``) are mounted inside it
        as hidden sub-frames. ``app.swap(name, variant)`` shows the chosen
        variant and hides the others, keeping surrounding sections fixed.

        Example::

            app.swap(
                "main",
                variants={
                    "dir":  [Layout().section("dir_tree")],
                    "file": [Layout().paired("left", "right", fill=Fill.BOTH,
                                             expand=True)],
                },
                default="dir",
            )
            layout = Layout().section("toolbar").target("main").section("status")
        """
        self._blocks.append(_Target(
            name=name,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
        ))
        return self

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
        """Start a grid block. Returns a fluent builder: ``cell(...)`` → ``end_grid()``.

        Example::

            Layout().grid()
                .cell("name_lbl", sticky="e")
                .cell("name", sticky="ew")
                .next_row()
                .cell("ok", colspan=3)
                .end_grid()

        ``GridBuilder.widget()`` is deprecated (0.4.13); use
        ``GridBuilder.cell()`` instead.
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
            if isinstance(block, _Row):
                out.update(block.widgets)
            elif isinstance(block, _Cluster):
                for entry in block.widgets:
                    out.add(entry.widget if isinstance(entry, Flex) else entry)
            elif isinstance(block, _Flow):
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

    def wrap(
        self,
        *widgets: str | Flex,
        gap: int | None = None,
        gapx: int | None = None,
        gapy: int | None = None,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Pack widgets in a wrapping flow (Flutter ``Wrap`` analog).

        Widgets are arranged left-to-right, top-to-bottom, wrapping to a new
        row whenever the next widget would not fit in the remaining frame
        width. Each widget keeps the width implied by its content or
        ``width=`` (e.g. an ``entry(width=30)`` stays wider than a short
        button) rather than being stretched to fill a column.

        Spacing is controlled by design-token keys from ``nextpytk.tokens.SPACE``:

        - ``gapx``: horizontal gap between items in a row.
        - ``gapy``: vertical gap between wrapped rows.

        When only ``gap`` is given it sets both ``gapx`` and ``gapy`` for
        backward compatibility, but ``gap`` is deprecated in favor of the
        explicit ``gapx``/``gapy`` pair. When nothing is given, gaps inherit
        the Layout's ``spacing`` setting.

        Pass a ``Flex(name, flex=...)`` to let a widget absorb leftover
        horizontal space in its row (Flutter ``Expanded`` analog)::

            from nextpytk.types import Flex

            Layout().wrap(
                "label",
                Flex("entry", flex=2),
                "search_btn",
                gapx=2,
            )

        **Implementation & constraints.** ``wrap`` positions its children with
        ``place`` (absolute x/y) because ``pack`` cannot reflow onto new rows:
        with ``pack -side left`` an overflowing child simply falls off the
        edge. Because it is ``place``-based:

        - All children share one parent frame and are ``place``-managed. They
          cannot also be ``pack``/``grid``-managed on the same master — mixing
          geometry managers on one frame raises ``TclError: conflicting
          geometry managers``.
        - Widths are computed from ``winfo_reqwidth()``; the frame uses
          ``pack_propagate(False)`` so its height is explicit.
        - On resize the flow is recomputed (children are ``place_forget``-ed
          and re-``place``-d) so rows re-wrap to the new width.
        - ``Flex`` only distributes a row's *leftover* space; it does not
          affect whether an item wraps.

        Example::

            Layout().wrap("tag1", "tag2", "tag3", "tag4")
        """
        ws: list[str | Flex] = list(widgets)
        base = gap if gap is not None else self.spacing
        gx = gapx if gapx is not None else base
        gy = gapy if gapy is not None else base
        _validate_gap(gx, "gapx")
        _validate_gap(gy, "gapy")
        self._blocks.append(_Cluster(
            widgets=ws,
            gap=gx,
            gapx=gx,
            gapy=gy,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx if padx is not None else self.padx,
            pady=pady if pady is not None else self.pady,
        ))
        return self

    def cluster(
        self,
        *widgets: str | Flex,
        gap: int | None = None,
        gapx: int | None = None,
        gapy: int | None = None,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Deprecated alias for :meth:`wrap`. Removed in nextpytk 0.5.0.

        ``cluster`` was renamed to ``wrap`` to match Flutter's layout widget
        vocabulary (``Wrap`` / ``Flex`` / ``Flow``). Please migrate call sites
        to :meth:`wrap`; the parameter set is identical.
        """
        warnings.warn(
            "Layout.cluster() is deprecated; use Layout.wrap() instead. "
            "cluster will be removed in nextpytk 0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.wrap(
            *widgets,
            gap=gap,
            gapx=gapx,
            gapy=gapy,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        )

    def flow(
        self,
        *widgets: str,
        delegate: FlowDelegate,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> Layout:
        """Place widgets with a custom :class:`FlowDelegate` (Flutter ``Flow`` analog).

        Positions and sizes are computed by ``delegate.compute_positions``
        given the available ``Constraints``; the frame height comes from
        ``delegate.compute_height``. On window resize the flow is recomputed,
        so the arrangement stays responsive.

        Example::

            from nextpytk.layout import FlowDelegate, Constraints

            class GridDelegate(FlowDelegate):
                def __init__(self, cols, gap=1):
                    self.cols = cols
                    self.gap = gap

                def compute_positions(self, children, constraints):
                    gap = tokens.SPACE[self.gap]
                    cell = (constraints.width - gap * (self.cols - 1)) // self.cols
                    return {
                        name: (i % self.cols * (cell + gap),
                               i // self.cols * (cell + gap),
                               cell, cell)
                        for i, name in enumerate(children)
                    }

            Layout().flow("a", "b", "c", "d", delegate=GridDelegate(cols=2))
        """
        self._blocks.append(_Flow(
            widgets=list(widgets),
            delegate=delegate,
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
        line_numbers: bool = False,
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

        ``line_numbers=True`` adds a read-only line-number gutter to each side.
        Both panes and both gutters then share a single vertical scrollbar, so
        the gutters always stay in lock-step with the content (no drift). Line
        numbers are logical rows of the text widget (``1..n``).

        .. note::
           ``line_numbers=True`` takes precedence over ``sync_yscroll``: the
           shared-scrollbar layout it installs always keeps the two panes (and
           both gutters) scrolled in lock-step, so passing
           ``sync_yscroll=False`` with ``line_numbers=True`` has no effect. If
           you need the panes to scroll independently, do **not** enable
           ``line_numbers``.

        Example::

            app.text("left", readonly=True, sync_yscroll_with="right")
            app.text("right", sync_yscroll_with="left")
            Layout().paired("left", "right", weight=(1, 1),
                            sync_yscroll=True, line_numbers=True)

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
            line_numbers=bool(line_numbers),
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
        # ``page_margin`` lets the caller override the default SPACE[6] pad.
        from nextpytk.theme import content_frame, window_header, status_bar
        from nextpytk import tokens as t
        page_margin = self.page_margin
        if page_margin is None:
            page_margin = t.SPACE[6]
        is_toplevel = isinstance(parent, tk.Tk) or getattr(parent, "winfo_toplevel", lambda: parent)() is parent
        bg_color = getattr(app, "theme_tokens", t.KIZASHI_LIGHT).bg

        if is_toplevel:
            body = content_frame(parent, padding=page_margin)
            app._content_frame = body
        else:
            # View/tab pages breathe too: inner content margin so sections
            # don't hug the notebook border (SPACE[6] / 24px page pad).
            body = tk.Frame(parent, bg=bg_color, bd=0, highlightthickness=0)
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
                # Register the section frame under a stable name so it is
                # addressable via hide_section()/show_section(). Prefer the
                # explicit ``name=`` from section(); otherwise derive one from
                # the first widget ("<first>_section"), which cannot collide
                # with a real widget name (widgets don't carry that suffix).
                section_key = block.name or (
                    f"{block.widgets[0]}_section" if block.widgets else None
                )
                if block.name is not None:
                    app._explicit_section_names.add(block.name)
                if section_key is not None:
                    app._section_frames[section_key] = frame
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
                row_jobs.append((frame, block))
            elif isinstance(block, _Paned):
                _ensure_allowed(block.name)
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx or 0, pady=block.pady or 0,
                )
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
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
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
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
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
                for entry in block.widgets:
                    name = entry.widget if isinstance(entry, Flex) else entry
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                # Defer packing until children exist; store the wrap block
                # on the frame for the Configure handler to re-layout.
                frame._cluster_block = block  # type: ignore[attr-defined]
                grid_jobs.append((frame, _Grid(cells={}, padx=0, pady=0)))
            elif isinstance(block, _Flow):
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
                for name in block.widgets:
                    _ensure_allowed(name)
                    app._widget_masters[name] = frame
                # Defer packing until children exist; store the flow block on
                # the frame for the Configure handler to re-layout.
                frame._flow_block = block  # type: ignore[attr-defined]
                grid_jobs.append((frame, _Grid(cells={}, padx=0, pady=0)))
            elif isinstance(block, _Paired):
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
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
            elif isinstance(block, _Target):
                # Reserve a swap region: create and pack the target frame, and
                # register it on the app so @app.swap variants can mount into
                # it. The frame itself is persistent; its variants are swapped.
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
                frame._swap_target = block.name  # type: ignore[attr-defined]
                app.register_swap_target(block.name, frame)
                row_jobs.append((frame, _Row(
                    widgets=[],
                    side="top", fill=block.fill, expand=block.expand,
                )))
            elif isinstance(block, _Nested):
                # Mount a new Frame, then recursively mount the nested Layout
                # inside it. The nested Layout manages its own frame hierarchy.
                frame = tk.Frame(body)
                frame.pack(
                    side=block.side, fill=block.fill, expand=block.expand,
                    padx=block.padx if block.padx is not None else 0,
                    pady=block.pady if block.pady is not None else 0,
                )
                frame.configure(bg=bg_color, bd=0, highlightthickness=0)
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
            child_side = row.child_side if n > 1 else row.side
            for name in row.widgets:
                tk_w = app._tk_widgets.get(name)
                if tk_w is None:
                    continue
                if n == 1:
                    tk_w.pack(side=child_side, padx=0, pady=0,
                              fill=row.fill, expand=row.expand)
                else:
                    # horizontal gap between siblings only (section frame
                    # already carries the outer rhythm). Last child hugs the
                    # right edge; all children share the available space when
                    # expand=True.
                    is_last = name == row.widgets[-1]
                    tk_w.pack(
                        side=child_side,
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
            # Wrap blocks are placed without stretching widths, not gridded.
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

            # Flow blocks: positions come from a custom FlowDelegate.
            fblock = getattr(_frame, "_flow_block", None)
            if isinstance(fblock, _Flow):
                _place_flow(app, _frame, fblock)
                _frame.bind(
                    "<Configure>",
                    lambda e, a=app, f=_frame, b=fblock: (
                        _place_flow(a, f, b) if e.widget == f else None
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
            # Grid raw tkinter widgets placed via cell_raw().
            for raw_w, opts in gb.raw_cells:
                grid_opts = {k: v for k, v in opts.items()
                             if k in ("row", "column", "sticky", "padx", "pady",
                                      "columnspan", "rowspan")}
                grid_opts["in_"] = _frame
                raw_w.grid(**grid_opts)
            # Wire cluster tab order via <Key-Tab> / <Shift-Key-Tab> bindings.
            # Tk has no native API to reorder focus traversal, so we intercept
            # the events and move focus in the visual row-major order.
            if gb.order:
                _wire_tab_order(app, _frame, gb.order)

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

    def cell(
        self,
        *names: str,
        sticky: str = "",
        padx: int | None = None,
        pady: int | None = None,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> _GridBuilder:
        """Place one or more widgets in horizontally consecutive cells.

        ``cell("a")`` places ``a`` at the current cursor position and is
        equivalent to ``widget("a")``.

        ``cell("a", "b", ...)`` places multiple widgets in a single row,
        starting at the current cursor position, one cell each. This is a
        convenience for the common case where the options are shared:

            Layout().grid().cell("name_lbl", "name", sticky="ew").end_grid()

        Restrictions when more than one name is given:

        * ``colspan`` and ``rowspan`` are not supported — each widget occupies
          exactly one cell. Passing them (or a pending ``.span(...)`` preset)
          raises ``ValueError``.

        ``colspan`` (single name only) overrides any previously-set colspan
        (via ``.span(...)``).
        """
        multiple = len(names) > 1
        if multiple and (colspan is not None or rowspan != 1 or self._colspan != 1):
            raise ValueError(
                "cell() with multiple names does not support colspan/rowspan; "
                "each widget occupies exactly one cell."
            )
        cs = colspan if colspan is not None else self._colspan
        for name in names:
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
            self._col += cs if cs > 1 else 1
        self._colspan = 1
        return self

    def cell_raw(
        self,
        widget: tk.Widget,
        *,
        sticky: str = "",
        padx: int | None = None,
        pady: int | None = None,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> _GridBuilder:
        """Place a raw tkinter widget at the current cursor position.

        Unlike ``cell()`` which takes a registered widget name, ``cell_raw()``
        accepts an already-created ``tk.Widget`` instance and grids it directly
        into the grid frame.  This is useful for mixing nextpytk's declarative
        widgets with hand-built tkinter frames or controls.

        Example::

            preview = ttk.Frame(...)
            Layout().grid()
                .cell("side_lbl", sticky="e")
                .cell("side", sticky="ew")
                .cell_raw(preview, rowspan=8, sticky="nsew")
                .end_grid()

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
        self._block.raw_cells.append((widget, opts))
        self._col += cs if cs > 1 else 1
        self._colspan = 1
        return self

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

        .. deprecated:: 0.4.13
           Use ``cell(name, ...)`` instead.

        ``colspan`` overrides any previously-set colspan (via ``.span(...)``).
        """
        warnings.warn(
            "GridBuilder.widget() is deprecated; use cell(name, ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.cell(
            name,
            sticky=sticky,
            padx=padx,
            pady=pady,
            colspan=colspan,
            rowspan=rowspan,
        )

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
                builder.cell("celsius", "fahrenheit", sticky="ew")
                builder.next_row().span(2).cell("note")
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

    def wrap(
        self,
        *widgets: str | Flex,
        gap: int | None = None,
        gapx: int | None = None,
        gapy: int | None = None,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> None:
        """Add a wrapping-flow block to the layout (see ``Layout.wrap``)."""
        self._layout.wrap(
            *widgets,
            gap=gap,
            gapx=gapx,
            gapy=gapy,
            side=side,
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        )

    def flow(
        self,
        *widgets: str,
        delegate: FlowDelegate,
        side: SideLike = "top",
        fill: FillLike = "x",
        expand: ExpandLike = False,
        padx: int | None = None,
        pady: int | None = None,
    ) -> None:
        """Add a flow block to the layout (see ``Layout.flow``)."""
        self._layout.flow(
            *widgets,
            delegate=delegate,
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
                builder.cell("a", "b")

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

    def cell(
        self,
        *names: str,
        sticky: str = "",
        padx: int | None = None,
        pady: int | None = None,
        colspan: int | None = None,
        rowspan: int = 1,
    ) -> None:
        """Place one or more widgets at the current grid cursor.

        ``cell("a", "b")`` places both widgets in horizontally consecutive
        cells with shared options. Multiple names do not support
        ``colspan``/``rowspan`` (raises ``ValueError``).
        """
        self._current_grid().cell(
            *names, sticky=sticky, padx=padx, pady=pady,
            colspan=colspan, rowspan=rowspan,
        )

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
        """Place a widget at the current grid cursor.

        .. deprecated:: 0.4.13
           Use ``cell(name, ...)`` instead.
        """
        warnings.warn(
            "LayoutBuilder.widget() is deprecated; use cell(name, ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.cell(
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
        """Set column span for the next cell() call."""
        self._current_grid().span(cols)
        return self

    # ── build ──

    def build(self) -> Layout:
        """Finalize and return the Layout."""
        while len(self._stack) > 1:
            self._pop_grid()
        return self._layout
