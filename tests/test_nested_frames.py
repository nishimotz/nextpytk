"""Tests for Layout.frame(nested Layout) support."""

from __future__ import annotations

import tkinter as tk

import pytest

from nextpytk import TkApp, Layout
from nextpytk import tokens as t

from .conftest import requires_display

pytestmark = requires_display


def _label_app():
    app = TkApp(title="t")

    @app.label("a")
    def a():
        return "A"

    @app.label("b")
    def b():
        return "B"

    @app.label("c")
    def c():
        return "C"

    @app.label("d")
    def d():
        return "D"

    return app


def _frame_for(app: TkApp, name: str) -> tk.Widget:
    """Return the section/nested frame that holds widget ``name``.

    For nested frames the frame is registered under the group name in
    ``app._tk_widgets``; for ordinary widgets it is the widget's immediate
    master.
    """
    w = app.widget(name)
    assert w is not None
    return w.master  # type: ignore[no-any-return]


def test_simple_nested_frame_creates_outer_frame(build):
    app = _label_app()
    inner = Layout().section("a", "b")
    build(app, layout=Layout().section("title").frame("group", inner))

    group = _frame_for(app, "a")
    assert isinstance(group, tk.Frame)
    # The nested frame's parent should be the body frame, not the root directly.
    # The title section has its own frame, so a and b share a different parent.
    a_parent = app.widget("a").master  # type: ignore[no-any-return]
    b_parent = app.widget("b").master  # type: ignore[no-any-return]
    assert a_parent is group
    assert b_parent is group


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def test_nested_widgets_are_packed_inside_group(build):
    app = _label_app()
    inner = Layout().section("a", "b")
    build(app, layout=Layout().frame("group", inner))

    group = _frame_for(app, "a")
    info = group.pack_info()  # type: ignore[no-any-return]
    assert info["side"] == "top"
    assert info["fill"] == "x"
    assert _as_int(info["padx"]) == t.SPACE[1]
    assert _as_int(info["pady"]) == t.SPACE[1]

    a_info = app.widget("a").pack_info()  # type: ignore[no-any-return]
    b_info = app.widget("b").pack_info()  # type: ignore[no-any-return]
    assert a_info["side"] == "left"
    assert a_info["in"] is group
    assert b_info["in"] is group


def test_nested_frame_pack_options(build):
    app = _label_app()
    inner = Layout().section("a")
    build(
        app,
        layout=Layout().frame(
            "group",
            inner,
            side="left",
            fill="both",
            expand=True,
            padx=0,
            pady=0,
        ),
    )

    group = app._tk_widgets["group"]
    info = group.pack_info()  # type: ignore[no-any-return]
    assert info["side"] == "left"
    assert info["fill"] == "both"
    assert info["expand"] == 1
    assert _as_int(info["padx"]) == 0
    assert _as_int(info["pady"]) == 0


def test_nested_layout_has_own_spacing(build):
    app = _label_app()
    inner = Layout(spacing=2).section("a", "b")
    build(app, layout=Layout(spacing=1).frame("group", inner))

    group = app._tk_widgets["group"]
    group_info = group.pack_info()  # type: ignore[no-any-return]
    assert _as_int(group_info["padx"]) == t.SPACE[1]
    assert _as_int(group_info["pady"]) == t.SPACE[1]

    a_info = app.widget("a").pack_info()  # type: ignore[no-any-return]
    assert a_info["padx"] == (0, t.SPACE[2])


def test_grid_inside_nested_frame(build):
    app = _label_app()
    inner = Layout().grid().widget("a").widget("b").end_grid()
    build(app, layout=Layout().frame("group", inner))

    group = _frame_for(app, "a")
    a_parent = app.widget("a").master  # type: ignore[no-any-return]
    b_parent = app.widget("b").master  # type: ignore[no-any-return]
    assert a_parent is group
    assert b_parent is group

    a_info = app.widget("a").grid_info()  # type: ignore[no-any-return]
    b_info = app.widget("b").grid_info()  # type: ignore[no-any-return]
    assert int(a_info["row"]) == 0
    assert int(a_info["column"]) == 0
    assert int(b_info["row"]) == 0
    assert int(b_info["column"]) == 1


def test_frame_inside_grid_block(build):
    app = _label_app()
    inner = Layout().section("c", "d")
    layout = Layout().grid().widget("a").widget("group", sticky="nsew").end_grid()
    layout.frame("group", inner)
    build(app, layout=layout)

    grid_frame = _frame_for(app, "a")
    group = app._tk_widgets["group"]
    # The nested group frame is packed into the top-level body, and its
    # inner content/row frames hold the actual widgets.
    assert app.widget("c").master.master.master is group  # type: ignore[no-any-return]
    assert app.widget("d").master.master.master is group  # type: ignore[no-any-return]

    group_info = group.grid_info()  # type: ignore[no-any-return]
    assert _as_int(group_info["row"]) == 0
    assert _as_int(group_info["column"]) == 1


def test_widget_names_includes_nested_layout(build):
    inner = Layout().section("a", "b").grid().widget("c").end_grid()
    outer = Layout().section("d").frame("group", inner)
    names = outer.widget_names()
    assert names == {"a", "b", "c", "d"}


def test_unknown_nested_widget_raises():
    app = _label_app()
    inner = Layout().section("a", "unknown")
    outer = Layout().frame("group", inner)
    # ``HeadlessHarness.build`` calls ``mount_frames`` without restricting
    # widgets, so the validation path used by multiview/stage layouts is not
    # exercised.  Call ``mount_frames_into`` directly with an explicit allow
    # list to verify that an unknown nested widget raises.
    # We create a dedicated, withdrawn root here because the default-root path
    # combined with an aborted mount leaves the Tk interpreter in a state that
    # breaks ``StringVar`` binding in later tests.
    root = tk.Tk()
    root.withdraw()
    app.set_root(root)
    try:
        with pytest.raises(ValueError, match="Widget 'unknown' is not allowed"):
            assert app._root is not None
            outer.mount_frames_into(app, app._root, allowed_widgets={"a"})
    finally:
        root.destroy()


def test_nested_frame_with_builder_api(build):
    from nextpytk.layout import LayoutBuilder

    app = _label_app()
    inner = LayoutBuilder()
    with inner:
        inner.section("a", "b")

    builder = LayoutBuilder()
    with builder:
        builder.section("title")
        builder.frame("group", inner.build())

    build(app, layout=builder.build())
    group = _frame_for(app, "a")
    assert app.widget("a").master is group  # type: ignore[no-any-return]
    assert app.widget("b").master is group  # type: ignore[no-any-return]
