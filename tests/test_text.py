"""Text widget public API and state sync."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_text_widget_returns_real_tk_text(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])

    real = app.text_widget("body")
    assert isinstance(real, tk.Text)
    # app.widget returns the outer container frame, not the tk.Text.
    container = app.widget("body")
    assert isinstance(container, (tk.Frame, ttk.Frame))
    assert container is not real


def test_text_get_returns_contents(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    app.text_set("body", "hello world")
    assert app.text_get("body") == "hello world"


def test_apply_state_updates_text_widget(build):
    app = TkApp(title="t")

    @app.text("preview", readonly=True)
    def preview(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["preview"])
    app.apply_state({"preview": "line one\nline two"})
    assert app.text_get("preview") == "line one\nline two"


def test_text_widget_skips_update_when_unchanged(build):
    app = TkApp(title="t")

    @app.text("preview", readonly=True)
    def preview(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["preview"])
    app.text_set("preview", "same")
    real = app.text_widget("preview")
    assert real is not None
    real.mark_set("insert", "1.2")
    app.apply_state({"preview": "same"})
    # Cursor position should be preserved because no actual replacement happened.
    assert real.index("insert") == "1.2"


def test_text_widget_unknown_name_returns_none(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert app.text_widget("no-such-widget") is None
    assert app.text_get("no-such-widget") == ""


def test_on_text_change_receives_actual_text(build):
    """Regression: _on_text_change must read from the real tk.Text, not the container."""
    app = TkApp(title="t")
    received = []

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        received.append(value)
        return {}

    build(app, layout=["body"])
    app.text_set("body", "typed contents")

    spec = next(s for s in app._widgets if s.kind == "text")
    app._on_text_change(spec, body)

    assert received == ["typed contents"]


def test_text_wrap_defaults_to_word(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "word"


def test_text_wrap_none_logical_lines(build):
    app = TkApp(title="t")

    @app.text("body", wrap="none")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "none"


def test_text_h_scroll_adds_horizontal_scrollbar(build):
    app = TkApp(title="t")

    @app.text("body", wrap="none", h_scroll=True)
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "none"
    # A horizontal scrollbar was created and wired to the text xview.
    hsb = app._text_hscrollbars.get("body")
    assert hsb is not None
    assert real.cget("xscrollcommand")


def test_text_without_h_scroll_has_no_hscrollbar(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert "body" not in app._text_hscrollbars
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("xscrollcommand") == ""

