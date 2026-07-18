"""Headless tests for @app.menubar."""

from __future__ import annotations

import tkinter as tk

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def _menubar(app: TkApp) -> tk.Menu:
    w = app.widget("menu")
    assert isinstance(w, tk.Menu), f"expected Menu, got {type(w).__name__}"
    return w


def test_menubar_creates_menu(build):
    app = TkApp(title="t")

    @app.menubar("menu")
    def menu_bar():
        return [
            {
                "label": "File",
                "items": [
                    {"label": "New", "command": "m_new"},
                    {"label": "Open", "command": "m_open"},
                    "---",
                    {"label": "Exit", "command": "m_exit"},
                ],
            },
        ]

    @app.button("m_new")
    def m_new(vals):
        return {"msg": "New"}

    build(app, layout=["m_new"])
    menubar = _menubar(app)
    assert str(menubar.type(0)) == "cascade"
    assert menubar.entrycget(0, "label") == "File"
    submenus = app._menubar_submenus.get("menu", [])
    assert len(submenus) >= 1
    file_menu = submenus[0]
    assert isinstance(file_menu, tk.Menu), f"expected Menu, got {type(file_menu).__name__}"
    assert str(file_menu.type(0)) == "command"
    assert file_menu.entrycget(0, "label") == "New"
    assert str(file_menu.type(2)) == "separator"
    assert str(file_menu.type(3)) == "command"
    assert file_menu.entrycget(3, "label") == "Exit"


def test_menubar_invokes_button_handler(build):
    app = TkApp(title="t")
    called: dict[str, str | None] = {"name": None}

    @app.menubar("menu")
    def menu_bar():
        return [{"label": "File", "items": [{"label": "Save", "command": "m_save"}]}]

    @app.button("m_save")
    def m_save(vals):
        called["name"] = "m_save"
        return {"msg": "saved"}

    build(app, layout=["m_save"])
    app._on_menubar_command("m_save", "Save")
    assert called["name"] == "m_save"
    assert app.state["msg"] == "saved"
    assert app.state["m_save"] == "Save"


def test_menubar_enabled_if_disables_item(build):
    app = TkApp(title="t")

    @app.menubar("menu")
    def menu_bar():
        return [
            {"label": "File", "items": [
                {"label": "Save", "command": "m_save",
                 "enabled_if": lambda vals: bool(vals.get("dirty"))},
            ]},
        ]

    @app.button("m_save")
    def m_save(vals):
        return {}

    build(app, layout=["m_save"], initial_state={"dirty": False})
    submenus = app._menubar_submenus.get("menu", [])
    file_menu = submenus[0]
    assert isinstance(file_menu, tk.Menu), f"expected Menu, got {type(file_menu).__name__}"
    assert str(file_menu.entrycget(0, "state")) == "disabled"

    app.apply_state({"dirty": True})
    assert str(file_menu.entrycget(0, "state")) == "normal"


def test_menubar_dynamic_items_rebuild_on_sync(build):
    app = TkApp(title="t")

    @app.menubar("menu")
    def menu_bar():
        if app.state.get("advanced"):
            return [
                {"label": "File", "items": [
                    {"label": "Basic", "command": "m_basic"},
                    {"label": "Advanced", "command": "m_advanced"},
                ]},
            ]
        return [{"label": "File", "items": [{"label": "Basic", "command": "m_basic"}]}]

    @app.button("m_basic")
    def m_basic(vals): return {}

    @app.button("m_advanced")
    def m_advanced(vals): return {}

    build(app, layout=["m_basic", "m_advanced"])
    menubar = _menubar(app)
    assert menubar.index("end") == 0

    app.apply_state({"advanced": True})
    assert menubar.index("end") == 0
    submenus = app._menubar_submenus.get("menu", [])
    file_menu = submenus[0]
    assert isinstance(file_menu, tk.Menu), f"expected Menu, got {type(file_menu).__name__}"
    assert file_menu.index("end") == 1
    assert file_menu.entrycget(1, "label") == "Advanced"


def test_menubar_schema_includes_items(build):
    app = TkApp(title="t")

    @app.menubar("menu")
    def menu_bar():
        return [{"label": "File", "items": [{"label": "New", "command": "m_new"}]}]

    @app.button("m_new")
    def m_new(vals): return {}

    build(app, layout=["m_new"])
    schema = app.schema()
    menubar = next(w for w in schema["widgets"] if w["kind"] == "menubar")
    assert menubar["items"] == [{"label": "File", "command": None, "items": [{"label": "New", "command": "m_new"}]}]
