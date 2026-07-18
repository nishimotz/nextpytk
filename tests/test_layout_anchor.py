"""Section anchoring: fill="none" sections must not float to the center."""

from __future__ import annotations

from nextpytk import TkApp, Layout

from .conftest import requires_display

pytestmark = requires_display


def _build_label_app(build, layout):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "short"

    return build(app, layout=layout)


def test_fill_none_section_anchors_west(build, harness):
    app = _build_label_app(build, Layout().section("msg", fill="none"))
    frame = app.widget("msg").master
    assert str(frame.pack_info()["anchor"]) == "w"


def test_multi_widget_fill_none_section_anchors_west(build):
    app = TkApp(title="t")

    @app.button("a", label="A")
    def a(vals):
        return {}

    @app.button("b", label="B")
    def b(vals):
        return {}

    build(app, layout=Layout().section("a", "b", fill="none"))
    frame = app.widget("a").master
    assert str(frame.pack_info()["anchor"]) == "w"


def test_explicit_center_anchor_is_honored(build):
    app = _build_label_app(
        build, Layout().section("msg", fill="none", anchor="center"))
    frame = app.widget("msg").master
    assert str(frame.pack_info()["anchor"]) == "center"


def test_fill_x_section_keeps_default_packing(build):
    app = _build_label_app(build, Layout().section("msg"))
    frame = app.widget("msg").master
    assert str(frame.pack_info()["fill"]) == "x"
