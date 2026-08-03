"""Regression tests for Layout.section(side=...) frame placement.

``section(..., side=...)`` must control where the section *frame* is packed in
its parent. Previously the frame pack side was hardcoded to "top", so a
``side="bottom"`` section (e.g. a status bar below an expandable body) was
ignored and the section could be pushed off-view by an ``expand=True``
sibling.

We also verify that the child pack side stays decoupled: a multi-widget
section lays its children out left-to-right ("left") while the frame itself
honours the requested placement side.
"""

from __future__ import annotations

from nextpytk import TkApp, Layout

from .conftest import requires_display

pytestmark = requires_display


def _build_app(build, layout) -> TkApp:
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "msg"

    @app.label("status")
    def status():
        return "status"

    return build(app, layout=layout)


def test_section_side_applies_to_frame(build):
    """``side="bottom"`` is honoured on the section frame pack call."""
    app = _build_app(
        build,
        Layout()
        .section("msg", fill="both", expand=True)
        .section("status", side="bottom", fill="x"),
    )
    status_frame = app.widget("status").master  # type: ignore[attr-defined]
    assert status_frame is not None
    info = status_frame.pack_info()  # type: ignore[no-any-return]
    assert str(info["side"]) == "bottom"


def test_section_default_side_is_top(build):
    """Default section frame side remains top."""
    app = _build_app(build, Layout().section("msg"))
    frame = app.widget("msg").master  # type: ignore[attr-defined]
    assert frame is not None
    info = frame.pack_info()  # type: ignore[no-any-return]
    assert str(info["side"]) == "top"


def test_multi_widget_children_side_left_frame_top(build):
    """A multi-widget section packs children left but keeps the frame on top."""
    app = TkApp(title="t")

    @app.button("a", label="A")
    def a(vals):
        return {}

    @app.button("b", label="B")
    def b(vals):
        return {}

    build(app, layout=Layout().section("a", "b"))
    frame = app.widget("a").master  # type: ignore[attr-defined]
    assert frame is not None
    assert str(frame.pack_info()["side"]) == "top"  # type: ignore[no-any-return]
    a_info = app.widget("a").pack_info()  # type: ignore[no-any-return]
    assert str(a_info["side"]) == "left"


def test_multi_widget_children_side_left_frame_bottom(build):
    """Multi-widget section: frame bottom, children still packed left."""
    app = TkApp(title="t")

    @app.button("a", label="A")
    def a(vals):
        return {}

    @app.button("b", label="B")
    def b(vals):
        return {}

    build(
        app,
        layout=Layout().section("a", "b", side="bottom", fill="x"),
    )
    frame = app.widget("a").master  # type: ignore[attr-defined]
    assert frame is not None
    assert str(frame.pack_info()["side"]) == "bottom"  # type: ignore[no-any-return]
    a_info = app.widget("a").pack_info()  # type: ignore[no-any-return]
    assert str(a_info["side"]) == "left"
