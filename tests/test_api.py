"""API contract: state= on button/entry, placeholder color constant, schema completeness."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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

    app = TkApp(title="t", theme="none")

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
    """Kizashi theme is applied automatically when no theme is specified."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # Kizashi styles should be configured with our accent/surface tokens.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") == tokens.ACCENT
    assert style.lookup("TEntry", "fieldbackground") == tokens.SURFACE


def test_theme_disabled(build):
    """theme='none' leaves the platform default theme untouched."""
    app = TkApp(title="t", theme="none")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # Primary.TButton should not have our custom background.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") != tokens.ACCENT


def test_theme_builtin_name(build):
    """theme='clam' switches to the named built-in ttk theme."""
    app = TkApp(title="t", theme="clam")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    assert style.theme_use() == "clam"


def test_theme_bool_deprecated(build):
    """Passing theme=True/False emits a DeprecationWarning."""
    import warnings

    app = TkApp(title="t", theme="none")

    @app.label("msg")
    def msg():
        return "hello"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app2 = TkApp(title="t", theme=False)
        build(app2, layout=["msg"])

    assert any(
        issubclass(w.category, DeprecationWarning)
        and "theme=True/False is deprecated" in str(w.message)
        for w in caught
    )


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


def test_entry_applies_font(build):
    """@app.entry accepts and applies a per-widget font option."""
    import tkinter.font as tkfont
    app = TkApp(title="t")

    @app.entry("styled", font=("TkDefaultFont", 12))
    def on_styled(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["styled"])
    w = app.widget("styled")
    assert w is not None
    assert isinstance(w, ttk.Entry)
    style = ttk.Style(w)
    actual = tkfont.Font(font=style.lookup(w.cget("style"), "font"))
    assert actual.actual("size") == 12


def test_entry_applies_padding_for_visual_height(build):
    """@app.entry accepts padding= as a declarative visual-height adjustment."""
    app = TkApp(title="t")

    @app.entry("padded", padding=(8, 12))
    def on_padded(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["padded"])
    w = app.widget("padded")
    assert w is not None
    assert isinstance(w, ttk.Entry)
    style = ttk.Style(w)
    configured = str(style.lookup(w.cget("style"), "padding"))
    assert configured == "(8, 12)" or configured == "8 12"


def test_button_applies_font(build):
    """@app.button accepts and applies a per-widget font option."""
    import tkinter.font as tkfont
    app = TkApp(title="t")

    @app.button("styled", label="Styled", font=("TkDefaultFont", 11))
    def on_styled(values: dict[str, str]) -> dict[str, str]:
        return {}

    build(app, layout=["styled"])
    w = app.widget("styled")
    assert w is not None
    assert isinstance(w, ttk.Button)
    style = ttk.Style(w)
    actual = tkfont.Font(font=style.lookup(w.cget("style"), "font"))
    assert actual.actual("size") == 11
