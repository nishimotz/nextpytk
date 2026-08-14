"""Tests for direct widget registration methods (add_*) and escape hatches."""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk

import pytest

from nextpytk import Layout, TkApp
from .conftest import requires_display

pytestmark = requires_display


def test_add_label_and_status(build):
    app = TkApp(title="test")
    app.add_label("lbl", text="Initial Label")
    app.add_status("stat", text="Ready")

    build(app, layout=["lbl", "stat"])

    lbl_w = app.get_widget("lbl")
    stat_w = app.widget("stat")
    assert isinstance(lbl_w, (tk.Label, ttk.Label))
    assert isinstance(stat_w, (tk.Label, ttk.Label))
    assert lbl_w.cget("text") == "Initial Label"
    assert stat_w.cget("text") == "Ready"

    app.apply_state({"lbl": "Updated Label", "stat": "Running"})
    assert lbl_w.cget("text") == "Updated Label"
    assert stat_w.cget("text") == "Running"


def test_add_entry_without_callback(build):
    app = TkApp(title="test")
    app.add_entry("username", placeholder="Enter name")
    app.add_status("msg", text="")

    @app.button("greet", label="Greet")
    def on_greet(values):
        return {"msg": f"Hello, {values['username']}!"}

    build(app, layout=["username", "greet", "msg"])

    entry_w = app.get_widget("username")
    assert isinstance(entry_w, (tk.Entry, ttk.Entry))
    app.apply_state({"username": "Alice"})

    greet_btn = app.widget("greet")
    assert isinstance(greet_btn, (tk.Button, ttk.Button))
    greet_btn.invoke()
    msg_w = app.get_widget("msg")
    assert msg_w is not None
    assert msg_w.cget("text") == "Hello, Alice!"


def test_add_button_with_and_without_callback(build):
    app = TkApp(title="test")
    clicked: list[str] = []

    app.add_button("noop_btn", label="No-Op")
    app.add_button("action_btn", label="Action", on_click=lambda vals: clicked.append("clicked") or {})

    build(app, layout=["noop_btn", "action_btn"])

    b_noop = app.get_widget("noop_btn")
    b_act = app.get_widget("action_btn")
    assert isinstance(b_noop, (tk.Button, ttk.Button))
    assert isinstance(b_act, (tk.Button, ttk.Button))
    assert b_noop.cget("text") == "No-Op"
    assert b_act.cget("text") == "Action"

    b_noop.invoke()
    assert clicked == []

    b_act.invoke()
    assert clicked == ["clicked"]


def test_add_checkbutton_and_radiobutton(build):
    app = TkApp(title="test")
    app.add_checkbutton("agree", text="I agree")
    app.add_radiobutton("opt_a", text="Option A", value="A", group="choice")
    app.add_radiobutton("opt_b", text="Option B", value="B", group="choice")
    app.add_status("status")

    @app.button("check_state", label="Check")
    def on_check(values):
        return {"status": f"agree={app.state.get('agree')} choice={app.state.get('choice')}"}

    build(app, layout=["agree", "opt_a", "opt_b", "check_state", "status"])

    assert isinstance(app.get_widget("agree"), (tk.Checkbutton, ttk.Checkbutton))
    assert isinstance(app.get_widget("opt_a"), (tk.Radiobutton, ttk.Radiobutton))


def test_add_text_with_content(build):
    app = TkApp(title="test")
    app.add_text("editor", content="Initial text content\nLine 2")

    build(app, layout=["editor"])

    text_container = app.get_widget("editor")
    assert text_container is not None
    text_inner = app._text_inner["editor"]
    assert "Initial text content" in text_inner.get("1.0", tk.END)


def test_add_other_widgets(build):
    app = TkApp(title="test")
    app.add_scale("slider", from_=0, to=50)
    app.add_spinbox("spinner", from_=1, to=10)
    app.add_combobox("dropdown", values=("Apple", "Banana"))
    app.add_listbox("items", items=("One", "Two"))
    app.add_treeview("table", columns=("id", "name"))
    app.add_progressbar("progress", length=150)
    app.add_canvas("draw", width=100, height=100)
    app.add_message("msg_box", text="Long message")
    app.add_filepicker("picker", label="Choose file")

    build(
        app,
        layout=[
            "slider", "spinner", "dropdown", "items", "table",
            "progress", "draw", "msg_box", "picker",
        ],
    )

    for name in ("slider", "spinner", "dropdown", "items", "table", "progress", "draw", "msg_box", "picker"):
        assert app.get_widget(name) is not None


def test_add_widgets_in_view_context(build):
    app = TkApp(title="test")

    with app.view("Tab1") as v:
        v.add_label("v_lbl", text="View Label")
        v.add_entry("v_entry", placeholder="View Entry")
        v.add_button("v_btn", label="View Button")

    assert "v_lbl" in app.view_widget_names("Tab1")
    assert "v_entry" in app.view_widget_names("Tab1")
    assert "v_btn" in app.view_widget_names("Tab1")


def test_escape_hatch_root_and_get_widget(build):
    app = TkApp(title="Escape Hatch Test")
    app.add_label("heading", text="Hello")

    build(app, layout=["heading"])

    # Root window access
    root = app.root
    assert root is not None
    assert isinstance(root, tk.Tk)

    # Widget access via both widget() and get_widget()
    w1 = app.widget("heading")
    w2 = app.get_widget("heading")
    assert w1 is not None
    assert w1 is w2
    assert isinstance(w1, (tk.Label, ttk.Label))

    # Direct raw Tkinter manipulation through escape hatch
    w1.configure({"text": "Changed Directly via Tk API"})
    assert w1.cget("text") == "Changed Directly via Tk API"


def test_escape_hatch_tcl_eval_and_call(build):
    app = TkApp(title="Tcl Escape Hatch")
    app.add_label("msg", text="Hello")

    build(app, layout=["msg"])

    # tcl interpreter property
    assert app.tcl is not None
    assert app.root is not None
    assert app.tcl is app.root.tk

    # eval raw Tcl
    res = app.eval("expr {10 + 20}")
    assert int(res) == 30

    app.eval("set greeting {Hello from Tcl!}")
    greeting = app.eval("set greeting")
    assert greeting == "Hello from Tcl!"

    # call Tcl command
    wm_title = app.call("wm", "title", ".")
    assert wm_title == "Tcl Escape Hatch"
