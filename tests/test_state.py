"""State dictionary: apply_state propagates to widgets, rejects non-dict, treeview rows/selection."""

from __future__ import annotations

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_label_reflects_state(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "initial"

    build(app, layout=["msg"])
    assert app.widget("msg").cget("text") == "initial"

    app.apply_state({"msg": "updated"})
    assert app.widget("msg").cget("text") == "updated"


def test_label_initial_dict_uses_own_name(build):
    """When the callback returns a dict, the widget's own name is the key used."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return {"other": "WRONG", "msg": "RIGHT"}

    build(app, layout=["msg"])
    assert app.widget("msg").cget("text") == "RIGHT"


def test_button_click_applies_state(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "before"

    @app.button("go", label="Go")
    def go(values):
        return {"msg": "after"}

    build(app, layout=["msg", "go"])
    app.widget("go").invoke()
    assert app.widget("msg").cget("text") == "after"
    assert app.state["msg"] == "after"


def test_treeview_rows_key_and_selection(build):
    app = TkApp(title="t")

    @app.treeview("files", columns=[("name", "Name"), ("size", "Size")])
    def on_select(idx):
        return {}

    build(app, layout=["files"],
          initial_state={"files_rows": [("a.txt", "1"), ("b.txt", "2")]})
    tree = app._treeview_inner["files"]
    assert len(tree.get_children()) == 2

    app.apply_state({"files": 1})
    sel = tree.selection()
    assert len(sel) == 1
    assert tree.index(sel[0]) == 1


def test_apply_state_rejects_non_dict(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"])
    with pytest.raises(TypeError):
        app.apply_state("just a string")  # type: ignore[arg-type]
