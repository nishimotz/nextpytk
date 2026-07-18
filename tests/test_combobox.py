"""Combobox widget tests."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from nextpytk import TkApp

from .conftest import requires_display


pytestmark = requires_display


def test_combobox_builds_with_values(build):
    app = TkApp(title="t")

    @app.combobox("folder", values=["INBOX", "Sent"])
    def on_folder(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["folder"])
    w = app.widget("folder")
    assert w is not None
    assert isinstance(w, ttk.Combobox)
    assert list(w.cget("values")) == ["INBOX", "Sent"]
    assert int(w.cget("width")) == 24  # DEFAULT_COMBOBOX_WIDTH


def test_combobox_applies_per_widget_font(build):
    app = TkApp(title="t")

    @app.combobox("styled", values=["A", "B"], font=("TkDefaultFont", 12))
    def on_styled(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["styled"])
    w = app.widget("styled")
    assert w is not None
    # ttk returns a font object/string for the "font" option; verify the configured size.
    import tkinter.font as tkfont
    actual = tkfont.Font(font=w.cget("font"))
    assert actual.actual("size") == 12


def test_combobox_readonly_state(build):
    app = TkApp(title="t")

    @app.combobox("priority", values=["Low", "High"], readonly=True)
    def on_priority(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["priority"])
    w = app.widget("priority")
    assert w is not None
    assert str(w.cget("state")) == "readonly"


def test_combobox_schema_includes_values_and_readonly():
    app = TkApp(title="t")

    @app.combobox("priority", values=["Low", "High"], readonly=True)
    def on_priority(value: str) -> dict[str, str]:
        return {}

    widget = app.schema()["widgets"][0]
    assert widget["kind"] == "combobox"
    assert widget["state_key"] == "priority"
    assert widget["values"] == ["Low", "High"]
    assert widget["readonly"] is True
