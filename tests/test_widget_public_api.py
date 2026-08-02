"""Public API additions for v0.4.4: widget_kwargs, layout_frame.

Covers the per-widget design-token override (``widget_kwargs``) and the
public layout-frame accessor (``layout_frame``).
"""

from __future__ import annotations

import tkinter as tk

from nextpytk import TkApp
from nextpytk import tokens as t

from .conftest import requires_display

pytestmark = requires_display


def test_layout_frame_returns_section_frame(build):
    app = TkApp(title="t")

    @app.button("ok", label="OK")
    def ok(_v: dict) -> dict:
        return {}

    build(app, layout=["ok"])
    frame = app.layout_frame("ok")
    assert isinstance(frame, (tk.Frame, tk.Misc))
    assert frame is not None


def test_layout_frame_unknown_returns_none(build):
    app = TkApp(title="t")

    @app.button("ok", label="OK")
    def ok(_v: dict) -> dict:
        return {}

    build(app, layout=["ok"])
    assert app.layout_frame("nope") is None


def test_widget_kwargs_button_font(build):
    app = TkApp(title="t")

    @app.button("ok", label="OK", widget_kwargs={"padx": 5, "pady": 3})
    def ok(_v: dict) -> dict:
        return {}

    build(app, layout=["ok"])
    # widget_kwargs are recorded in extras.
    spec = next(s for s in app._widgets if s.name == "ok")
    assert spec.extras["widget_kwargs"] == {"padx": 5, "pady": 3}


def test_widget_kwargs_text_bg(build):
    app = TkApp(title="t")

    @app.text("body", widget_kwargs={"bg": "#112233"})
    def body(value: str) -> dict:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    # The tk.Text bg is overridden from the theme default.
    assert real.cget("bg") == "#112233"


def test_widget_kwargs_invalid_key_ignored(build):
    """Invalid/unknown widget_kwargs keys should not abort widget construction."""
    app = TkApp(title="t")

    @app.button("ok", label="OK", widget_kwargs={"not_an_option": 1})
    def ok(_v: dict) -> dict:
        return {}

    build(app, layout=["ok"])
    w = app.widget("ok")
    assert w is not None
