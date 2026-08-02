"""Decorator argument validation (v0.4.4).

Invalid enum-like / numeric options are rejected at registration time with
a clear ``ValueError`` instead of a cryptic ``_tkinter.TclError`` at runtime.
"""

from __future__ import annotations

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_invalid_text_wrap_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid wrap"):
        @app.text("body", wrap="wrapped")
        def body(value: str) -> dict:
            return {}


def test_invalid_text_state_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid state"):
        @app.text("body", state="read")
        def body(value: str) -> dict:
            return {}


def test_invalid_scale_orient_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid orient"):
        @app.scale("vol", orient="diagonal")
        def vol(value: str) -> dict:
            return {}


def test_invalid_listbox_selectmode_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid selectmode"):
        @app.listbox("lst", selectmode="single-select")
        def lst(idx: int) -> dict:
            return {}


def test_invalid_treeview_selectmode_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid selectmode"):
        @app.treeview("tree", columns=[("c", "C")], selectmode="all")
        def tree(idx: int) -> dict:
            return {}


def test_invalid_filepicker_mode_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid mode"):
        @app.filepicker("fp", mode="pick")
        def fp(path) -> dict:
            return {}


def test_invalid_progressbar_mode_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid mode"):
        @app.progressbar("pb", mode="infinite")
        def pb():
            return {}


def test_invalid_paned_orient_raises():
    app = TkApp(title="t")
    with pytest.raises(ValueError, match="invalid orient"):
        app.paned("pd", panes=("a", "b"), orient="slanted")
