"""Tests for Layout.cluster() (wrapping-flow Cluster)."""

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


def _cluster_frame(app: TkApp, name: str) -> tk.Frame:
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
    """Cluster uses place; widgets are not gridded or packed."""
    app = _tag_app()
    build(app, layout=Layout().cluster("a", "b", "c", "d"))

    w = app.widget("a")
    assert w is not None
    # In place mode the widget's geometry manager is "place".
    assert w.winfo_manager() == "place"  # type: ignore[no-any-return]
    assert w.master is not None


def test_cluster_wraps_into_rows(build):
    """With a tiny frame width all widgets fall onto their own rows."""
    app = _tag_app()
    build(app, layout=Layout().cluster("a", "b", "c", "d"))

    frame = _cluster_frame(app, "a")
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
    build(app, layout=Layout(spacing=2).cluster("a", "b"))

    frame = _cluster_frame(app, "a")
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert info["padx"] == t.SPACE[2]
    assert info["pady"] == t.SPACE[2]


def test_cluster_explicit_gap_overrides_layout_default(build):
    """gap controls widget spacing, not the cluster frame padding."""
    app = _tag_app()
    build(app, layout=Layout(spacing=2).cluster("a", "b", gap=1))

    frame = _cluster_frame(app, "a")
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


def test_cluster_invalid_gap_raises():
    with pytest.raises(ValueError, match="Cluster gap=99"):
        Layout().cluster("a", gap=99)


def test_cluster_widget_names(build):
    layout = Layout().cluster("a", "b", "c").section("d")
    assert layout.widget_names() == {"a", "b", "c", "d"}


def test_cluster_frame_is_packed(build):
    app = _tag_app()
    build(app, layout=Layout().cluster("a", "b", "c", "d", fill="both", expand=True))

    frame = _cluster_frame(app, "a")
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert info["fill"] == "both"
    assert info["expand"] == 1


def test_cluster_tab_order_follows_visual_row_major(build):
    """Tab order should traverse cluster cells row-by-row, not creation order.

    Cluster widgets get a custom bindtag (``ClusterTab*``) that intercepts
    ``<Key-Tab>`` / ``<Shift-Key-Tab>`` to move focus in visual row-major
    order. We verify the bindtag is present on each cluster child.
    """
    app = _tag_app()
    build(app, layout=Layout().cluster("d", "b", "c", "a"))

    frame = _cluster_frame(app, "a")
    for name in ("a", "b", "c", "d"):
        w = app.widget(name)
        assert w is not None
        tags = list(w.bindtags())
        cluster_tags = [t for t in tags if t.startswith("ClusterTab")]
        assert len(cluster_tags) == 1, f"{name}: expected 1 ClusterTab tag, got {cluster_tags}"
