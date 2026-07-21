"""Dynamic listbox items_key and combobox values_key sync."""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from typing import Any

from nextpytk import TkApp

from tests.conftest import requires_display

pytestmark = requires_display


def test_listbox_items_key_refreshes_contents(build):
    app = TkApp(title="t")

    @app.listbox("results", items_key="results_items")
    def on_select(idx: int) -> dict[str, Any]:
        return {}

    build(app, layout=["results"], initial_state={"results_items": ["a", "b"]})
    w = app.widget("results")
    assert isinstance(w, tk.Listbox)
    assert [w.get(i) for i in range(w.size())] == ["a", "b"]

    app.apply_state({"results_items": ["x", "y", "z"]})
    assert [w.get(i) for i in range(w.size())] == ["x", "y", "z"]


def test_listbox_items_key_clamps_selection(build):
    app = TkApp(title="t")

    @app.listbox("results", items_key="results_items")
    def on_select(idx: int) -> dict[str, Any]:
        return {}

    build(
        app,
        layout=["results"],
        initial_state={"results_items": ["a", "b", "c"], "results": 2},
    )
    w = app.widget("results")
    assert isinstance(w, tk.Listbox)
    assert w.curselection() == (2,)

    app.apply_state({"results_items": ["only"]})
    assert [w.get(i) for i in range(w.size())] == ["only"]
    assert app.state["results"] == -1
    assert w.curselection() == ()


def test_listbox_without_items_key_ignores_name_items_update(build):
    """Static listbox must not treat {name}_items as a dynamic source."""
    app = TkApp(title="t")

    @app.listbox("files", items=["a", "b"])
    def on_select(idx: int) -> dict[str, Any]:
        return {}

    build(app, layout=["files"])
    w = app.widget("files")
    assert isinstance(w, tk.Listbox)
    assert [w.get(i) for i in range(w.size())] == ["a", "b"]

    app.apply_state({"files_items": ["hijacked"]})
    assert [w.get(i) for i in range(w.size())] == ["a", "b"]


def test_combobox_values_key_refreshes_choices(build):
    app = TkApp(title="t")

    @app.combobox("folder", values_key="folder_values")
    def on_folder(value: str) -> dict[str, Any]:
        return {}

    build(
        app,
        layout=["folder"],
        initial_state={"folder_values": ["INBOX", "Sent"]},
    )
    w = app.widget("folder")
    assert isinstance(w, ttk.Combobox)
    assert list(w.cget("values")) == ["INBOX", "Sent"]

    app.apply_state({"folder_values": ["Drafts", "Trash"]})
    assert list(w.cget("values")) == ["Drafts", "Trash"]


def test_combobox_values_key_clears_stale_selection(build):
    app = TkApp(title="t")

    @app.combobox("folder", values_key="folder_values", key="folder")
    def on_folder(value: str) -> dict[str, Any]:
        return {}

    build(
        app,
        layout=["folder"],
        initial_state={
            "folder_values": ["INBOX", "Sent"],
            "folder": "INBOX",
        },
    )
    w = app.widget("folder")
    assert isinstance(w, ttk.Combobox)
    assert w.get() == "INBOX"

    app.apply_state({"folder_values": ["Drafts"]})
    assert list(w.cget("values")) == ["Drafts"]
    assert w.get() == ""
    assert app.state["folder"] == ""
