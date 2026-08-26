"""Tests for the declarative sync map and automatic a11y coupling."""

from __future__ import annotations

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_sync_map_structure(build):
    app = TkApp(title="t")

    app.add_label("msg", text="")
    app.add_button("go", label="Go")
    app.add_text("notes")
    app.add_progressbar("progress")
    app.add_treeview("results", columns=["id", "name"])
    app.add_combobox("combo", values=["a", "b"])
    app.add_checkbutton("flag", label="Flag")
    app.add_radiobutton("r1", label="R1", group_key="grp")
    app.add_scale("vol", from_=0, to=10)
    app.add_spinbox("n", from_=0, to=10)
    app.add_listbox("items_list", items=["x", "y"])

    build(app, layout=["msg", "go", "notes", "progress", "results", "combo", "flag", "r1", "vol", "n", "items_list"])

    sm = app.sync_map()

    # Label / button sync by name.
    assert ("msg" in sm and any(s.name == "msg" and "text" in p for s, p in sm["msg"]))
    assert ("go" in sm and any(s.name == "go" and "text" in p for s, p in sm["go"]))
    assert ("notes" in sm and any(s.name == "notes" and "text" in p for s, p in sm["notes"]))

    # Progressbar: state_key (progress) + mode + running.
    assert any(s.name == "progress" and "value" in p for s, p in sm["progress"])
    assert "progress_mode" in sm
    assert "progress_running" in sm

    # Treeview: rows + selection.
    assert "results_rows" in sm
    assert any(s.name == "results" and "selection" in p for s, p in sm["results"])

    # Combobox: values + value (when values_key not set, static values used).
    assert "combo" in sm
    assert any("value" in p for s, p in sm["combo"])

    # Checkbutton / radiobutton / scale / spinbox / listbox.
    assert "items_list" in sm
    assert "flag" in sm
    assert "radio" in sm  # radiobutton lives under its group key
    assert "vol" in sm
    assert "n" in sm

def test_sync_map_respects_sync_false(build):
    app = TkApp(title="t")
    app.add_label("msg", text="", sync=False)
    build(app)
    assert app.sync_map() == {}

def test_apply_state_emits_a11y_for_text_and_selection(build):
    """State changes should auto-emit a11y events for text and selection."""
    app = TkApp(title="t")

    app.add_label("msg", text="hello")
    app.add_listbox("pick", items=["a", "b"])

    build(app, layout=["msg", "pick"])

    # Skip if a11y not supported (Tk < 9.1).
    if app._a11y.acc_supported is False:
        pytest.skip("a11y requires Tk 9.1+")

    calls: list[tuple] = []
    orig_call = app._call_accessible

    def spy(*args):
        calls.append(args)
        return orig_call(*args)

    app._call_accessible = spy  # type: ignore[method-assign]

    try:
        app.apply_state({"msg": "world"})

        assert any("set_acc_value" in str(c) for c in calls), calls

        calls.clear()

        app.apply_state({"pick": 1})

        assert any("emit_selection_change" in str(c) for c in calls), calls
    finally:
        app._call_accessible = orig_call  # type: ignore[method-assign]
