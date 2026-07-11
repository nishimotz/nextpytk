"""listbox enabled_if: content updates must apply while disabled (du-flat-async regression)."""

from __future__ import annotations

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def _make_app(flag: dict):
    app = TkApp(title="t")

    @app.listbox("files", enabled_if=lambda vals: not flag["busy"])
    def on_select(value):
        return {}

    @app.status("msg")
    def msg():
        return "idle"

    return app


def test_listbox_content_updates_while_disabled(build):
    """Regression: state=disabled makes Tk ignore programmatic delete/insert."""
    flag = {"busy": False}
    app = _make_app(flag)
    build(app, layout=["files", "msg"])

    w = app.widget("files")
    w.insert("end", "old-1", "old-2")

    flag["busy"] = True
    app.apply_state({"msg": "scanning"})  # enabled_if=False → 選択不可へ

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

    w = app.widget("files")
    assert str(w.cget("selectmode")) == "none"
    assert str(w.cget("state")) == "normal"

    flag["busy"] = False
    app.apply_state({"msg": "idle"})
    assert str(w.cget("selectmode")) == "browse"


def test_listbox_disable_clears_selection(build):
    flag = {"busy": False}
    app = _make_app(flag)
    build(app, layout=["files", "msg"])

    w = app.widget("files")
    w.insert("end", "a", "b")
    w.selection_set(0)
    assert w.curselection() == (0,)

    flag["busy"] = True
    app.apply_state({"msg": "scanning"})
    assert w.curselection() == ()
