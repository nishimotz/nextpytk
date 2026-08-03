"""Tests for Layout.wrap() / Layout.flow() and the Flex/FlowDelegate helpers."""

from __future__ import annotations

import tkinter as tk

import pytest

from nextpytk import TkApp, Layout
from nextpytk import tokens as t
from nextpytk.layout import _cluster_rows

from .conftest import requires_display

pytestmark = requires_display


def _tag_app():
    app = TkApp(title="t")

    @app.button("a")
    def a(values):
        return {}

    @app.button("b")
    def b(values):
        return {}

    @app.button("c")
    def c(values):
        return {}

    @app.button("d")
    def d(values):
        return {}

    return app


def _wrap_frame(app: TkApp, name: str) -> tk.Frame:
    w = app.widget(name)
    assert w is not None
    return w.master  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    "widths,gap,avail,expected",
    [
        ([10, 10, 10, 10], 0, 19, [["a0"], ["a1"], ["a2"], ["a3"]]),
        ([10, 10, 10, 10], 0, 40, [["a0", "a1", "a2", "a3"]]),
        ([10, 10, 10, 10], 5, 55, [["a0", "a1", "a2", "a3"]]),
        ([10, 10, 10, 10], 5, 54, [["a0", "a1", "a2"], ["a3"]]),
        ([20, 30, 40], 0, 90, [["a0", "a1", "a2"]]),
        ([20, 30, 40], 0, 89, [["a0", "a1"], ["a2"]]),
        ([], 0, 100, []),
    ],
)
def test_cluster_rows(widths, gap, avail, expected):
    names = [f"a{i}" for i in range(len(widths))]
    rows = _cluster_rows(names, widths, gap, avail)
    assert rows == expected


def test_cluster_places_widgets_at_natural_width(build):
    """Wrap uses place; widgets are not gridded or packed."""
    app = _tag_app()
    build(app, layout=Layout().wrap("a", "b", "c", "d"))

    w = app.widget("a")
    assert w is not None
    # In place mode the widget's geometry manager is "place".
    assert w.winfo_manager() == "place"  # type: ignore[no-any-return]
    assert w.master is not None


def test_cluster_wraps_into_rows(build):
    """With a tiny frame width all widgets fall onto their own rows."""
    app = _tag_app()
    build(app, layout=Layout().wrap("a", "b", "c", "d"))

    frame = _wrap_frame(app, "a")
    # Headless frame has no real width, so each widget gets its own row.
    # place assigns a distinct y coordinate to each row.
    y_positions = {
        name: app._tk_widgets[name].place_info()["y"]
        for name in ("a", "b", "c", "d")
    }
    unique_ys = set(y_positions.values())
    assert len(unique_ys) == 4, f"expected 4 distinct rows, got {unique_ys}"


def test_cluster_inherits_layout_spacing(build):
    app = _tag_app()
    build(app, layout=Layout(spacing=2).wrap("a", "b"))

    frame = _wrap_frame(app, "a")
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert info["padx"] == t.SPACE[2]
    assert info["pady"] == t.SPACE[2]


def test_cluster_explicit_gap_overrides_layout_default(build):
    """gapx/gapy control widget spacing, not the wrap frame padding."""
    app = _tag_app()
    build(app, layout=Layout(spacing=2).wrap("a", "b", gapx=1, gapy=1))

    frame = _wrap_frame(app, "a")
    # The cluster frame padding still inherits Layout.spacing.
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert info["padx"] == t.SPACE[2]
    assert info["pady"] == t.SPACE[2]
    # Headless frame width is tiny, so widgets are on separate rows.
    # The vertical gap between rows equals t.SPACE[1].
    a_info = app._tk_widgets["a"].place_info()
    b_info = app._tk_widgets["b"].place_info()
    a_y = int(a_info["y"])
    a_h = int(a_info["height"])
    b_y = int(b_info["y"])
    assert b_y == a_y + a_h + t.SPACE[1]


def test_wrap_invalid_gap_raises():
    with pytest.raises(ValueError, match="Cluster gapx=99"):
        Layout().wrap("a", gapx=99)


def test_cluster_deprecated_alias(build):
    """Using the legacy ``cluster()`` name emits a DeprecationWarning."""
    app = _tag_app()
    with pytest.warns(DeprecationWarning, match="Layout.cluster\\(\\) is deprecated"):
        build(app, layout=Layout().cluster("a", "b", gap=1))


def test_wrap_gapx_gapy_stored_independently(build):
    """gapx and gapy are resolved independently on the wrap block."""
    from nextpytk.layout import _Wrap

    layout = Layout().wrap("a", "b", "c", gapx=2, gapy=1)
    block = next(b for b in layout._blocks if isinstance(b, _Wrap))
    assert block.gapx == 2
    assert block.gapy == 1

    # Default: gapx and gapy fall back to Layout.spacing.
    layout2 = Layout(spacing=3).wrap("a", "b")
    block2 = next(b for b in layout2._blocks if isinstance(b, _Wrap))
    assert block2.gapx == 3
    assert block2.gapy == 3


def test_wrap_widget_names(build):
    layout = Layout().wrap("a", "b", "c").section("d")
    assert layout.widget_names() == {"a", "b", "c", "d"}


def test_wrap_frame_is_packed(build):
    app = _tag_app()
    build(app, layout=Layout().wrap("a", "b", "c", "d", fill="both", expand=True))

    frame = _wrap_frame(app, "a")
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert info["fill"] == "both"
    assert info["expand"] == 1


def test_cluster_tab_order_follows_visual_row_major(build):
    """Tab order should traverse wrap cells row-by-row, not creation order.

    Wrap widgets get a custom bindtag (``TabOrder*``) that intercepts
    ``<Key-Tab>`` / ``<Shift-Key-Tab>`` to move focus in visual row-major
    order. We verify the bindtag is present on each wrap child.
    """
    app = _tag_app()
    build(app, layout=Layout().wrap("d", "b", "c", "a"))

    frame = _wrap_frame(app, "a")
    for name in ("a", "b", "c", "d"):
        w = app.widget(name)
        assert w is not None
        tags = list(w.bindtags())
        tab_tags = [t for t in tags if t.startswith("TabOrder")]
        assert len(tab_tags) == 1, f"{name}: expected 1 TabOrder tag, got {tab_tags}"


def test_wrap_tab_order_includes_entry_and_text(build):
    """Entry and Text children participate in the Tab cycle by default.

    Focus follows the visual order, so Tab moves focus through every child —
    including single-line Entry and multiline Text (the handler returns
    ``break`` before a tab character is inserted). No registered child becomes
    keyboard-unreachable.
    """
    from nextpytk.types import Fill

    app = _tag_app()

    @app.entry("name", placeholder="Name", width=30)
    def on_name(value):
        return {}

    @app.text("body")
    def on_text(value):
        return {}

    build(app, layout=Layout().wrap("a", "name", "b", "body", "c", fill=Fill.X))

    # Buttons AND the entry get a TabOrder tag.
    for name in ("a", "b", "c", "name"):
        w = app.widget(name)
        assert w is not None
        tab_tags = [t for t in w.bindtags() if t.startswith("TabOrder")]
        assert len(tab_tags) == 1, f"{name}: expected 1 TabOrder tag"
    # Multiline Text is also in the cycle: its inner tk.Text gets a tag.
    text_w = app._text_inner.get("body")
    assert text_w is not None
    tab_tags = [t for t in text_w.bindtags() if t.startswith("TabOrder")]
    assert len(tab_tags) == 1, "text should participate in the Tab cycle"


# ── Flex (Flutter Expanded analog) ──


def test_wrap_flex_widget_names(build):
    """Flex-wrapped names are collected by widget_names."""
    from nextpytk.types import Flex

    layout = Layout().wrap("a", Flex("b", flex=2), "c")
    assert layout.widget_names() == {"a", "b", "c"}


def test_wrap_flex_absorbs_leftover_width(build):
    """A Flex item in a wide frame is wider than its natural request width."""
    from nextpytk.types import Flex
    from nextpytk.layout import _place_cluster, _Cluster

    app = _tag_app()
    layout = Layout().wrap("a", Flex("b", flex=1), "c", gapx=1, gapy=1)
    build(app, layout=layout)

    frame = _wrap_frame(app, "a")
    frame.configure(width=800, height=100)
    frame.update_idletasks()

    # Re-run placement as the <Configure> handler would.
    block = next(b for b in layout._blocks if isinstance(b, _Cluster))
    _place_cluster(app, frame, block)

    a_info = app._tk_widgets["a"].place_info()
    b_info = app._tk_widgets["b"].place_info()
    assert int(b_info["width"]) > int(a_info["width"])


# ── Flow (Flutter Flow analog) ──


def test_flow_places_widgets_from_delegate(build):
    """Flow positions widgets according to a FlowDelegate."""
    from nextpytk.layout import FlowDelegate, Constraints, _Flow

    class StackDelegate(FlowDelegate):
        def compute_positions(self, children, constraints):
            return {name: (0, 0, 100, 50) for name in children}

    app = _tag_app()
    build(
        app,
        layout=Layout().flow(
            "a", "b", "c", delegate=StackDelegate(), padx=0, pady=0,
        ),
    )

    w = app.widget("a")
    assert w is not None
    assert w.winfo_manager() == "place"  # type: ignore[no-any-return]
    info = w.place_info()
    assert int(info["x"]) == 0
    assert int(info["width"]) == 100


def test_flow_block_registered(build):
    """flow() appends a _Flow block and reports widget names."""
    from nextpytk.layout import FlowDelegate, _Flow

    class Delegate(FlowDelegate):
        def compute_positions(self, children, constraints):
            return {}

    layout = Layout().flow("a", "b", delegate=Delegate())
    assert any(isinstance(b, _Flow) for b in layout._blocks)
    assert layout.widget_names() == {"a", "b"}
