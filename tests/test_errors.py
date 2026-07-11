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


def test_duplicate_widget_name_raises(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    with pytest.raises(ValueError, match="msg"):
        @app.button("msg", label="dup")
        def other(values):
            return {}


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
