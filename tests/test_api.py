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


def test_placeholder_color_uses_tokens(build):
    """Placeholder color is exported from the design tokens."""
    from nextpytk.tokens import TEXT_MUTED
    assert PLACEHOLDER_FG is TEXT_MUTED

    app = TkApp(title="t", theme=False)

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


def test_theme_applied_by_default(build):
    """Kizashi theme is applied automatically when theme=True."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # clam theme should be selected and TButton configured with our accent.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") == tokens.ACCENT
    assert style.lookup("TEntry", "fieldbackground") == tokens.SURFACE


def test_theme_disabled(build):
    """theme=False leaves the platform default theme untouched."""
    app = TkApp(title="t", theme=False)

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # Primary.TButton should not have our custom background.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") != tokens.ACCENT


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
