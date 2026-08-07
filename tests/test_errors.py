"""Error policy: callbacks must never be silently swallowed."""

from __future__ import annotations

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_callback_error_prints_traceback(build, capsys):
    app = TkApp(title="t")

    @app.button("boom", label="Boom")
    def boom(values):
        raise RuntimeError("kaboom")

    build(app, layout=["boom"])
    app.widget("boom").invoke()

    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "kaboom" in err


def test_callback_error_reraises_in_debug_mode(build):
    """With debug=True, exceptions are re-raised up to the Tk callback boundary.

    invoke() goes through report_callback_exception which swallows the error,
    so we call the handler directly (inside the Tcl boundary).
    """
    app = TkApp(title="t", debug=True)

    @app.button("boom", label="Boom")
    def boom(values):
        raise RuntimeError("kaboom")

    build(app, layout=["boom"])
    spec = app.widget_specs(kind="button")[0]
    with pytest.raises(RuntimeError, match="kaboom"):
        app._on_button_click(spec, spec.on_click)


def test_duplicate_widget_name_replaces_in_place(build):
    """Re-registering a name silently replaces the previous spec (latest wins)."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "first"

    @app.button("msg", label="dup")
    def other(values):
        return {}

    # The button replaced the label spec in place.
    assert app.widget_kind("msg") == "button"
    specs = app.widget_specs()
    assert len(specs) == 1
    assert specs[0].kind == "button"
    assert specs[0].label_text == "dup"


def test_re_register_same_kind_replaces_callback(build):
    """Re-decorating the same button name swaps the callback and options."""
    app = TkApp(title="t")

    @app.button("next", label="次へ")
    def first(values):
        return {"n": 1}

    @app.button("next", label="Go")
    def second(values):
        return {"n": 2}

    specs = app.widget_specs(kind="button")
    assert len(specs) == 1
    assert specs[0].label_text == "Go"
    assert specs[0].on_click is second


def test_unregister_removes_spec(build):
    app = TkApp(title="t")

    @app.button("next", label="次へ")
    def on_next(values):
        return {}

    assert app.widget_kind("next") == "button"
    assert app.unregister("next") is True
    assert app.widget_kind("next") is None
    assert app.widget_specs() == []
    # Unregistering a missing name returns False.
    assert app.unregister("next") is False


def test_unregister_then_re_register(build):
    """unregister + re-register lets a name change kind cleanly."""
    app = TkApp(title="t")

    @app.button("next", label="次へ")
    def on_next(values):
        return {}

    app.unregister("next")

    @app.label("next")
    def next_label():
        return ""

    assert app.widget_kind("next") == "label"


def test_bind_may_share_name_with_button():
    """A bind and a button may share the same name (the bind annotates the button with its shortcut)."""
    app = TkApp(title="t")

    @app.button("save", label="Save")
    def save_btn(values):
        return {}

    @app.bind("save", sequence="<Control-s>", label="Ctrl+S")
    def save_key(state):
        return {}

    assert app.widget_kind("save") == "button"
