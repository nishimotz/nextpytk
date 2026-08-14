"""Tests for ThemeTokens, dark theme, custom theme tokens, and load_theme_tcl."""

from __future__ import annotations

from dataclasses import replace
import tkinter as tk
import tkinter.ttk as ttk

import pytest

from nextpytk import (
    KIZASHI_DARK,
    KIZASHI_LIGHT,
    Layout,
    ThemeTokens,
    TkApp,
)
from .conftest import requires_display

pytestmark = requires_display


def test_builtin_theme_tokens():
    assert KIZASHI_LIGHT.name == "kizashi"
    assert KIZASHI_LIGHT.bg == "#faf8f4"
    assert KIZASHI_LIGHT.accent == "#7a5a34"

    assert KIZASHI_DARK.name == "kizashi-dark"
    assert KIZASHI_DARK.bg == "#1e1e1e"
    assert KIZASHI_DARK.accent == "#d4a373"
    assert KIZASHI_DARK.text == "#f0ebe4"


def test_dark_theme_application(build):
    app = TkApp(title="Dark Theme Test", theme="kizashi-dark")
    app.add_label("lbl", text="Dark Label")
    app.add_button("btn", label="Dark Button")

    build(app, layout=["lbl", "btn"])

    assert app.theme_tokens is KIZASHI_DARK
    assert app.root is not None
    assert app.root.cget("bg") == KIZASHI_DARK.bg


def test_custom_theme_tokens(build):
    custom_theme = replace(
        KIZASHI_LIGHT,
        name="my-custom-blue",
        bg="#f0f4f8",
        accent="#0066cc",
        on_accent="#ffffff",
    )

    app = TkApp(title="Custom Theme Test", theme=custom_theme)
    app.add_label("lbl", text="Custom Label")

    build(app, layout=["lbl"])

    assert app.theme_tokens is custom_theme
    assert app.theme_tokens.accent == "#0066cc"
    assert app.root is not None
    assert app.root.cget("bg") == "#f0f4f8"


def test_load_theme_tcl_inline(build):
    app = TkApp(title="Tcl Theme Test")
    app.add_label("lbl", text="Tcl Themed")

    build(app, layout=["lbl"])

    tcl_theme_script = """
    ttk::style theme create test_tcl_theme -parent default -settings {
        ttk::style configure . -background #e0e0e0
    }
    """
    app.load_theme_tcl(tcl_theme_script, theme_name="test_tcl_theme")

    assert app.root is not None
    style = ttk.Style(app.root)
    assert style.theme_use() == "test_tcl_theme"


def test_load_theme_tcl_deferred(build):
    app = TkApp(title="Deferred Tcl Theme Test")
    app.add_label("lbl", text="Deferred Tcl")

    tcl_theme_script = """
    ttk::style theme create deferred_tcl_theme -parent default -settings {
        ttk::style configure . -background #d0d0d0
    }
    """
    # Call before build/run (deferred)
    app.load_theme_tcl(tcl_theme_script, theme_name="deferred_tcl_theme")

    build(app, layout=["lbl"])

    assert app.root is not None
    style = ttk.Style(app.root)
    assert style.theme_use() == "deferred_tcl_theme"
