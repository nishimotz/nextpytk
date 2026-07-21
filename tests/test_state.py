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


def test_button_click_allows_no_arg_callback(build):
    """Button callbacks may omit values when they do not need input."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "before"

    @app.button("go", label="Go")
    def go():
        return {"msg": "after"}

    build(app, layout=["msg", "go"])
    app.widget("go").invoke()
    assert app.widget("msg").cget("text") == "after"


def test_entry_allows_no_arg_callback(build):
    """Entry callbacks may omit value when only buttons read values[name]."""
    app = TkApp(title="t")

    @app.entry("name")
    def on_name():
        return {}

    @app.button("go", label="Go")
    def go(values):
        return {"echo": values["name"]}

    @app.label("echo")
    def echo():
        return ""

    build(app, layout=["name", "go", "echo"])
    app.widget("name").insert(0, "Taro")
    app.widget("go").invoke()
    assert app.widget("echo").cget("text") == "Taro"


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


def test_unknown_state_key_warns_and_suggests(build, capsys):
    """Unknown state keys print a warning with a Levenshtein suggestion."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"])
    app.apply_state({"mgs": "typo"})
    err = capsys.readouterr().err
    assert "unknown state key 'mgs'" in err
    assert "Did you mean 'msg'?" in err


def test_unknown_state_key_raises_in_debug_mode(build):
    app = TkApp(title="t", debug=True)

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"])
    with pytest.raises(KeyError, match="mgs"):
        app.apply_state({"mgs": "typo"})


def test_app_defined_state_key_does_not_warn(build, capsys):
    """Keys far from any widget name are intentional app state (e.g. 'tab')."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"])
    app.apply_state({"tab": "Button", "e_mirror_text": "x"})
    assert capsys.readouterr().err == ""


def test_initial_state_keys_never_warn(build, capsys):
    """initial_state declares the app schema — even near-miss keys are OK."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"], initial_state={"mgs": "intentional"})
    app.apply_state({"mgs": "again"})
    assert capsys.readouterr().err == ""


def test_typo_warning_fires_once(build, capsys):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    build(app, layout=["msg"])
    app.apply_state({"mgs": "typo"})
    app.apply_state({"mgs": "typo2"})
    err = capsys.readouterr().err
    assert err.count("unknown state key 'mgs'") == 1
