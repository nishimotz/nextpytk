"""listbox enabled_if: content updates must apply while disabled (du-flat-async regression)."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from nextpytk import TkApp
from nextpytk.types import EventSeq

from .conftest import requires_display

pytestmark = requires_display


def _make_app(flag: dict):
    app = TkApp(title="t")

    @app.listbox("files", enabled_if=lambda vals: not flag["busy"])
    def on_select(idx):
        return {}

    @app.status("msg")
    def msg():
        return "idle"

    return app


def _listbox(app: TkApp) -> tk.Listbox:
    w = app.widget("files")
    assert isinstance(w, tk.Listbox), f"expected Listbox, got {type(w).__name__}"
    return w


def test_listbox_content_updates_while_disabled(build):
    """Regression: state=disabled makes Tk ignore programmatic delete/insert."""
    flag = {"busy": False}
    app = _make_app(flag)
    build(app, layout=["files", "msg"])

    w = _listbox(app)
    w.insert("end", "old-1", "old-2")

    flag["busy"] = True
    app.apply_state({"msg": "scanning"})  # enabled_if=False → selection disabled

    # Simulate background job completion: swap content while disabled
    w.delete(0, "end")
    w.insert("end", "new-1", "new-2", "new-3")
    assert [w.get(i) for i in range(w.size())] == ["new-1", "new-2", "new-3"]

    flag["busy"] = False
    app.apply_state({"msg": "idle"})
    assert w.size() == 3


def test_listbox_disable_blocks_selection_not_state(build):
    """Disable via selectmode=none (per docstring), keep state=normal."""
    flag = {"busy": True}
    app = _make_app(flag)
    build(app, layout=["files", "msg"])
    app.apply_state({"msg": "scanning"})

    w = _listbox(app)
    assert str(w.cget("selectmode")) == "none"
    assert str(w.cget("state")) == "normal"

    flag["busy"] = False
    app.apply_state({"msg": "idle"})
    assert str(w.cget("selectmode")) == "browse"


def test_listbox_disable_clears_selection(build):
    flag = {"busy": False}
    app = _make_app(flag)
    build(app, layout=["files", "msg"])

    w = _listbox(app)
    w.insert("end", "a", "b")
    w.selection_set(0)
    assert w.curselection() == (0,)

    flag["busy"] = True
    app.apply_state({"msg": "scanning"})
    assert w.curselection() == ()


def test_listbox_events_receive_state_and_apply_update(build):
    """Declarative events= handlers receive state and can apply_state."""
    app = TkApp(title="t")

    @app.status("msg")
    def msg():
        return "idle"

    @app.listbox(
        "files",
        items=["a", "b", "c"],
        events={
            EventSeq.RETURN: lambda state: {"msg": f"return:{state.get('files', '')}"},
        },
    )
    def on_select(idx):
        return {}

    build(app, layout=["files", "msg"], initial_state={"msg": "idle"})
    spec = app._spec("files")
    assert spec is not None
    handler = spec.extras["events"][EventSeq.RETURN]
    app._on_listbox_event(handler)
    assert app.state["msg"] == "return:-1"


def test_listbox_event_handler_receives_current_state(build):
    """Widget-level event handler sees state values set before the event."""
    app = TkApp(title="t")

    @app.status("msg")
    def msg():
        return "idle"

    @app.listbox(
        "files",
        items=["x"],
        events={
            EventSeq.DELETE: lambda state: {"msg": state.get("marker", "missing")},
        },
    )
    def on_select(idx):
        return {}

    build(app, layout=["files", "msg"], initial_state={"msg": "idle", "marker": "deleted"})
    spec = app._spec("files")
    assert spec is not None
    handler = spec.extras["events"]["<Delete>"]
    app._on_listbox_event(handler)
    assert app.state["msg"] == "deleted"


def test_listbox_callback_receives_selected_index(build):
    """Callback receives the selected integer index, not the display string."""
    app = TkApp(title="t")

    @app.listbox("files", items=["alpha", "beta", "gamma"])
    def on_select(idx: int):
        return {}

    build(app, layout=["files"])
    w = app.widget("files")
    assert isinstance(w, tk.Listbox)

    spec = app._spec("files")
    assert spec is not None

    # No selection yet → callback receives -1 when fired via internal handler.
    app._on_listbox_select(spec, on_select)
    assert app.state["files"] == -1

    w.selection_set(1)
    app._on_listbox_select(spec, on_select)
    assert app.state["files"] == 1

    w.selection_clear(0, "end")
    app._on_listbox_select(spec, on_select)
    assert app.state["files"] == -1
