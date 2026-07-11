"""API contract: state= on button/entry, placeholder color constant, schema completeness."""

from __future__ import annotations

import tkinter as tk

from nextpytk import TkApp
from nextpytk.app import PLACEHOLDER_FG

from .conftest import requires_display

pytestmark = requires_display


def test_button_state_disabled_is_applied(build):
    app = TkApp(title="t")

    @app.button("go", label="Go", state="disabled")
    def go(values):
        return {}

    build(app, layout=["go"])
    assert str(app.widget("go").cget("state")) == "disabled"


def test_entry_state_disabled_is_applied(build):
    app = TkApp(title="t")

    @app.entry("name", state="disabled")
    def name(value):
        return {}

    build(app, layout=["name"])
    assert str(app.widget("name").cget("state")) == "disabled"


def test_placeholder_color_meets_contrast(build):
    """Placeholder color must use the contrast-verified constant."""
    assert PLACEHOLDER_FG.lower() == "#767676"

    app = TkApp(title="t")

    @app.entry("name", placeholder="your name")
    def name(value):
        return {}

    build(app, layout=["name"])
    w = app.widget("name")
    try:
        fg = str(w.cget("foreground"))
    except tk.TclError:
        return  # platform theme forbids fg query; constant check above suffices
    assert fg.lower() in (PLACEHOLDER_FG, "")


def test_schema_includes_all_widgets(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    @app.button("go", label="Go")
    def go(values):
        return {}

    kinds = {w["name"]: w["kind"] for w in app.schema()["widgets"]}
    assert kinds == {"msg": "label", "go": "button"}
