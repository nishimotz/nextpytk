"""Tests for @app.filepicker declarative file dialogs."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_filepicker_open_sets_state(build):
    app = TkApp(title="t")

    @app.filepicker("open_path", mode="open", title="Open file")
    def pick(path: str | None) -> dict[str, Any]:
        return {"open_path": path}

    build(app, layout=["open_path"])
    schema = app.schema()
    picker = next(w for w in schema["widgets"] if w["name"] == "open_path")
    assert picker["kind"] == "filepicker"
    assert picker["mode"] == "open"
    assert picker["title"] == "Open file"

    with patch("tkinter.filedialog.askopenfilename", return_value="/tmp/foo.txt"):
        w = app.widget("open_path")
        assert w is not None
        assert hasattr(w, "invoke")
        w.invoke()  # type: ignore[no-any-expr]

    assert app.state["open_path"] == "/tmp/foo.txt"


def test_filepicker_cancel_returns_none(build):
    app = TkApp(title="t")

    @app.filepicker("open_path", mode="open")
    def pick(path: str | None) -> dict[str, Any]:
        return {"open_path": path}

    build(app, layout=["open_path"])

    with patch("tkinter.filedialog.askopenfilename", return_value=""):
        w = app.widget("open_path")
        assert w is not None
        assert hasattr(w, "invoke")
        w.invoke()  # type: ignore[no-any-expr]

    assert app.state["open_path"] is None


def test_filepicker_open_multiple_returns_list(build):
    app = TkApp(title="t")

    @app.filepicker("paths", mode="open_multiple")
    def pick(paths: list[str] | None) -> dict[str, Any]:
        return {"paths": paths}

    build(app, layout=["paths"])

    selected = ["/tmp/a.txt", "/tmp/b.txt"]
    with patch("tkinter.filedialog.askopenfilenames", return_value=selected):
        w = app.widget("paths")
        assert w is not None
        assert hasattr(w, "invoke")
        w.invoke()  # type: ignore[no-any-expr]

    assert app.state["paths"] == selected


def test_filepicker_directory_mode(build):
    app = TkApp(title="t")

    @app.filepicker("dir", mode="directory", title="Choose folder")
    def pick(path: str | None) -> dict[str, Any]:
        return {"dir": path}

    build(app, layout=["dir"])

    with patch("tkinter.filedialog.askdirectory", return_value="/tmp/"):
        w = app.widget("dir")
        assert w is not None
        assert hasattr(w, "invoke")
        w.invoke()  # type: ignore[no-any-expr]

    assert app.state["dir"] == "/tmp/"


def test_filepicker_save_mode(build):
    app = TkApp(title="t")

    @app.filepicker("save_path", mode="save", defaultextension=".txt")
    def pick(path: str | None) -> dict[str, Any]:
        return {"save_path": path}

    build(app, layout=["save_path"])
    schema = app.schema()
    picker = next(w for w in schema["widgets"] if w["name"] == "save_path")
    assert picker["mode"] == "save"
    assert picker["defaultextension"] == ".txt"

    with patch("tkinter.filedialog.asksaveasfilename", return_value="/tmp/out.txt"):
        w = app.widget("save_path")
        assert w is not None
        assert hasattr(w, "invoke")
        w.invoke()  # type: ignore[no-any-expr]

    assert app.state["save_path"] == "/tmp/out.txt"


def test_filepicker_via_menubar_command(build):
    """A menubar item whose command is a filepicker name opens the dialog."""
    app = TkApp(title="t")

    @app.filepicker("open_file", mode="open", title="Open file")
    def pick(path: str | None) -> dict[str, Any]:
        return {"open_path": path}

    @app.menubar("menu")
    def menu_bar():
        return [
            {"label": "File", "items": [
                {"label": "Open...", "command": "open_file"},
            ]},
        ]

    build(app, layout=["open_file"])

    with patch("tkinter.filedialog.askopenfilename", return_value="/tmp/foo.txt"):
        app._on_menubar_command("open_file", "Open...")

    assert app.state["open_path"] == "/tmp/foo.txt"