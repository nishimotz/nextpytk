"""Tests for enabled_if referencing app state and values."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from nextpytk import TkApp
from .conftest import requires_display


@requires_display
def test_enabled_if_sees_state_single_arg(build):
    """enabled_if receiving a single argument can read both state and entry values."""
    app = TkApp(title="test")

    app.add_entry("q")

    # Button enabled only when selected_row in state >= 0
    @app.button(
        "action_btn",
        label="Action",
        enabled_if=lambda ctx: ctx.get("selected_row", -1) >= 0,
    )
    def on_action(vals: dict[str, Any]) -> dict[str, Any]:
        return {}

    built = build(app, layout=["q", "action_btn"], initial_state={"selected_row": -1})
    btn = built.widget("action_btn")
    assert btn is not None
    assert str(btn.cget("state")) == "disabled"

    # Select a row via state update
    built.apply_state({"selected_row": 0})
    assert str(btn.cget("state")) == "normal"

    # Deselect row
    built.apply_state({"selected_row": -1})
    assert str(btn.cget("state")) == "disabled"


@requires_display
def test_enabled_if_two_args_signature(build):
    """enabled_if with (values, state) signature receives entry values and state dicts."""
    app = TkApp(title="test")

    app.add_entry("q")

    # Enabled when entry 'q' is non-empty and state 'ready' is True
    @app.button(
        "run_btn",
        label="Run",
        enabled_if=lambda vals, state: bool(vals.get("q")) and bool(state.get("ready")),
    )
    def on_run(vals: dict[str, Any]) -> dict[str, Any]:
        return {}

    built = build(app, layout=["q", "run_btn"], initial_state={"ready": False})
    btn = built.widget("run_btn")
    assert btn is not None
    assert str(btn.cget("state")) == "disabled"

    # Set state ready to True, but q is still empty -> still disabled
    built.apply_state({"ready": True})
    assert str(btn.cget("state")) == "disabled"

    # Set entry value 'q'
    built.apply_state({"q": "search-term"})
    assert str(btn.cget("state")) == "normal"

    # Set ready back to False
    built.apply_state({"ready": False})
    assert str(btn.cget("state")) == "disabled"


@requires_display
def test_enabled_if_listbox_from_state(build):
    """listbox enabled_if uses selectmode='none' when disabled by state."""
    app = TkApp(title="test")

    @app.listbox(
        "items",
        items=["apple", "banana"],
        enabled_if=lambda ctx: bool(ctx.get("allowed")),
    )
    def on_select(idx: int) -> dict[str, Any]:
        return {}

    built = build(app, layout=["items"], initial_state={"allowed": False})
    lb = built.widget("items")
    assert lb is not None
    assert str(lb.cget("selectmode")) == "none"
    assert str(lb.cget("state")) == "normal"  # programmatic updates still allowed

    built.apply_state({"allowed": True})
    assert str(lb.cget("selectmode")) == "browse"


@requires_display
def test_menubar_item_enabled_if_sees_state(build):
    """Menubar item enabled_if can check app state."""
    app = TkApp(title="test")

    @app.menubar("menu")
    def menu_bar():
        return [
            {
                "label": "File",
                "items": [
                    {
                        "label": "Save",
                        "command": "on_save",
                        "enabled_if": lambda ctx: bool(ctx.get("has_changes")),
                    }
                ],
            }
        ]

    @app.button("on_save")
    def on_save(vals):
        return {"has_changes": False}

    built = build(app, layout=["on_save"], initial_state={"has_changes": False})
    menubar = built.widget("menu")
    assert isinstance(menubar, tk.Menu)
    sub = built._menubar_submenus["menu"][0]
    assert isinstance(sub, tk.Menu)

    # Initially has_changes is False -> disabled
    assert sub.entrycget(0, "state") == "disabled"

    # State updated -> normal
    built.apply_state({"has_changes": True})
    assert sub.entrycget(0, "state") == "normal"
