"""Layout-level spacing overrides."""

from __future__ import annotations

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

    return app


def _section_frame(app: TkApp, name: str):
    w = app.widget(name)
    assert w is not None
    return w.master  # type: ignore[no-any-return]


def _content_frame(app: TkApp, name: str):
    """Return the outermost content_frame that wraps the named widget's section."""
    frame = _section_frame(app, name)
    root = frame.winfo_toplevel()
    while frame is not root and frame.master is not root:
        frame = frame.master  # type: ignore[assignment]
    return frame


def _cget_int(w, option: str) -> int:
    value = w.cget(option)
    if isinstance(value, str):
        return int(value)
    if isinstance(value, (tuple, list)):
        # padding may be (l, r, t, b) or (x, y); use the first element.
        return int(value[0])
    return int(value)


def _pack_info(app: TkApp, name: str):
    return _section_frame(app, name).pack_info()  # type: ignore[no-any-return]


def _grid_info_ints(app: TkApp, name: str):
    w = app.widget(name)
    assert w is not None
    info = w.grid_info()  # type: ignore[no-any-return]
    def _int(value: object) -> int:
        assert isinstance(value, int)
        return value
    return {"padx": _int(info["padx"]), "pady": _int(info["pady"])}


def test_layout_default_spacing_is_token_1(build):
    app = _label_app()
    build(app, layout=Layout().section("a"))
    info = _pack_info(app, "a")
    assert int(info["padx"]) == t.SPACE[1]
    assert int(info["pady"]) == t.SPACE[1]


def test_layout_spacing_2_doubles_block_padding(build):
    app = _label_app()
    build(app, layout=Layout(spacing=2).section("a"))
    info = _pack_info(app, "a")
    assert int(info["padx"]) == t.SPACE[2]
    assert int(info["pady"]) == t.SPACE[2]


def test_section_explicit_padx_pady_override_layout_default(build):
    app = _label_app()
    build(app, layout=Layout(spacing=2).section("a", padx=t.SPACE[4], pady=t.SPACE[3]))
    info = _pack_info(app, "a")
    assert int(info["padx"]) == t.SPACE[4]
    assert int(info["pady"]) == t.SPACE[3]


def test_grid_block_inherits_layout_spacing(build):
    app = _label_app()
    layout = Layout(spacing=3).grid().widget("a").widget("b").end_grid()
    build(app, layout=layout)
    info = _pack_info(app, "a")
    assert int(info["padx"]) == t.SPACE[3]
    assert int(info["pady"]) == t.SPACE[3]


def test_grid_widget_inherits_layout_spacing(build):
    app = _label_app()
    layout = Layout(spacing=3).grid().widget("a").widget("b").end_grid()
    build(app, layout=layout)
    a_info = _grid_info_ints(app, "a")
    b_info = _grid_info_ints(app, "b")
    assert a_info["padx"] == t.SPACE[3]
    assert a_info["pady"] == t.SPACE[3]
    assert b_info["padx"] == t.SPACE[3]
    assert b_info["pady"] == t.SPACE[3]


def test_grid_widget_explicit_pad_overrides_layout_default(build):
    app = _label_app()
    layout = Layout(spacing=3).grid().widget("a", padx=t.SPACE[1], pady=t.SPACE[1]).widget("b").end_grid()
    build(app, layout=layout)
    a_info = _grid_info_ints(app, "a")
    b_info = _grid_info_ints(app, "b")
    assert a_info["padx"] == t.SPACE[1]
    assert a_info["pady"] == t.SPACE[1]
    assert b_info["padx"] == t.SPACE[3]
    assert b_info["pady"] == t.SPACE[3]


def test_horizontal_sibling_gap_uses_section_padx(build):
    app = _label_app()
    build(app, layout=Layout(spacing=2).section("a", "b"))
    a_w = app.widget("a")
    b_w = app.widget("b")
    assert a_w is not None and hasattr(a_w, "pack_info")
    assert b_w is not None and hasattr(b_w, "pack_info")
    a_info = a_w.pack_info()  # type: ignore[no-any-return]
    b_info = b_w.pack_info()  # type: ignore[no-any-return]
    assert a_info["padx"] == (0, t.SPACE[2])
    assert b_info["padx"] == 0


def test_layout_padx_pady_direct_override(build):
    app = _label_app()
    build(app, layout=Layout(padx=t.SPACE[4], pady=t.SPACE[3]).section("a"))
    info = _pack_info(app, "a")
    assert int(info["padx"]) == t.SPACE[4]
    assert int(info["pady"]) == t.SPACE[3]


def test_layout_invalid_spacing_raises(build):
    try:
        Layout(spacing=5)
    except ValueError as exc:
        assert "5" in str(exc)
        assert "SPACE token" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid spacing token")


def test_from_list_inherits_layout_spacing(build):
    app = _label_app()
    layout = Layout(spacing=2)
    layout.section("a").section("b")
    build(app, layout=layout)
    a_info = _pack_info(app, "a")
    b_info = _pack_info(app, "b")
    assert int(a_info["pady"]) == t.SPACE[2]
    assert int(b_info["pady"]) == t.SPACE[2]


def test_layout_page_margin_default_is_space6(build):
    """The top-level content_frame page pad defaults to SPACE[6] (24px)."""
    app = _label_app()
    build(app, layout=Layout().section("a"))
    content = _content_frame(app, "a")
    assert _cget_int(content, "padding") == t.SPACE[6]


def test_layout_page_margin_zero(build):
    """page_margin=0 removes the page pad from the content_frame."""
    app = _label_app()
    build(app, layout=Layout(page_margin=0).section("a"))
    content = _content_frame(app, "a")
    assert _cget_int(content, "padding") == 0


def test_layout_page_margin_explicit(build):
    """page_margin accepts an explicit pixel override."""
    app = _label_app()
    build(app, layout=Layout(page_margin=8).section("a"))
    content = _content_frame(app, "a")
    assert _cget_int(content, "padding") == 8
