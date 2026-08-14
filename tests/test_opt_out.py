"""Unit tests for opt-out mechanisms: sync=False, Layout.container(), and app.untracked()."""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import pytest

from nextpytk import Layout, TkApp
from .conftest import requires_display

pytestmark = requires_display


def test_sync_false_text_widget(build):
    app = TkApp(title="Unsynced Text")
    app.add_text("log_viewer", sync=False)
    app.add_button("trigger", label="Trigger")

    build(app, layout=["log_viewer", "trigger"])

    raw_text = app.get_widget("log_viewer")
    assert isinstance(raw_text, (tk.Text, ttk.Frame, tk.Frame))
    inner = app._text_inner["log_viewer"]

    # Manually insert text imperatively
    inner.insert("1.0", "Imperative log output")

    # Apply state that targets other keys or even the same key
    app.apply_state({"log_viewer": "Should be ignored", "status": "running"})

    # Content must NOT be overwritten by apply_state
    assert inner.get("1.0", "end-1c") == "Imperative log output"


def test_sync_false_entry_widget(build):
    app = TkApp(title="Unsynced Entry")
    app.add_entry("manual_input", sync=False)

    build(app, layout=["manual_input"])

    raw_entry = app.get_widget("manual_input")
    assert isinstance(raw_entry, (tk.Entry, ttk.Entry))

    raw_entry.insert(0, "User typing")

    # Apply state targeting this key
    app.apply_state({"manual_input": "New value"})

    # Must retain user typing because sync=False
    assert raw_entry.get() == "User typing"

    # Reading values must still return the actual content
    values = app._entry_values_dict()
    assert values["manual_input"] == "User typing"


def test_layout_container_pack(build):
    app = TkApp(title="Pack Container Test")
    app.add_label("header_lbl", text="Top Header")

    layout = (
        Layout()
        .section("header_lbl")
        .container("chart_area", fill="both", expand=True)
    )

    build(app, layout=layout)

    chart_frame = app.container("chart_area")
    assert isinstance(chart_frame, tk.Frame)

    # Mount custom raw tkinter widgets manually
    custom_lbl = tk.Label(chart_frame, text="Raw Widget inside Container")
    custom_lbl.pack()
    assert custom_lbl.winfo_parent() == str(chart_frame)


def test_layout_container_grid(build):
    app = TkApp(title="Grid Container Test")
    app.add_label("sidebar", text="Sidebar")

    layout = (
        Layout()
        .grid()
            .cell("sidebar", sticky="w")
            .container("canvas_slot", sticky="nsew")
        .end_grid()
    )

    build(app, layout=layout)

    canvas_frame = app.container("canvas_slot")
    assert isinstance(canvas_frame, tk.Frame)

    # Mount custom raw canvas
    raw_canvas = tk.Canvas(canvas_frame, width=100, height=100)
    raw_canvas.pack(fill="both", expand=True)
    assert raw_canvas.winfo_parent() == str(canvas_frame)


def test_app_untracked_context(build):
    app = TkApp(title="Untracked Context Test", ingest_trace=True)
    app.add_entry("inp")

    build(app, layout=["inp"])

    assert app._ingest_trace is True
    with app.untracked():
        assert app._ingest_trace is False
    assert app._ingest_trace is True
