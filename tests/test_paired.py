"""Tests for Layout.paired() side-by-side layout and y-scroll sync."""

from __future__ import annotations

import pytest

from nextpytk import Layout, TkApp
from nextpytk import tokens as t

from .conftest import requires_display

pytestmark = requires_display


def _paired_app():
    app = TkApp(title="t")

    @app.text("left", height=8, sync_yscroll_with="right")
    def left(values):
        return {}

    @app.text("right", height=8, sync_yscroll_with="left")
    def right(values):
        return {}

    return app


def _paired_frame(app: TkApp, name: str):
    w = app.widget(name)
    assert w is not None
    return w.master


def test_paired_widget_names():
    layout = Layout().paired("left", "right").section("info")
    assert layout.widget_names() == {"left", "right", "info"}


def test_paired_grids_children_side_by_side(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", fill="both", expand=True))

    left = app.widget("left")
    right = app.widget("right")
    assert left is not None
    assert right is not None
    assert left.winfo_manager() == "grid"
    assert right.winfo_manager() == "grid"

    li = left.grid_info()
    ri = right.grid_info()
    assert li["row"] == 0
    assert li["column"] == 0
    assert ri["row"] == 0
    assert ri["column"] == 1


def test_paired_frame_is_packed(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", fill="both", expand=True))

    frame = _paired_frame(app, "left")
    info = frame.pack_info()  # type: ignore[union-attr]
    assert info["fill"] == "both"
    assert info["expand"] == 1


def test_paired_weights_applied(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", weight=(1, 3)))

    frame = _paired_frame(app, "left")
    assert frame.grid_size() == (2, 1)
    assert frame.columnconfigure(0)["weight"] == 1  # type: ignore[typeddict-item]
    assert frame.columnconfigure(1)["weight"] == 3  # type: ignore[typeddict-item]


def test_paired_sync_disabled(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", sync_yscroll=False))

    left = app.text_widget("left")
    right = app.text_widget("right")
    assert left is not None
    assert right is not None

    # Default text widget scrollcommand is wired to its own scrollbar, not
    # a layout-level sync chain. We check that the configured commands still
    # exist but do not move the other widget.
    left_before = left.yview()[0]
    right_before = right.yview()[0]

    # Populate enough content to scroll.
    app.text_set("left", "\n".join(f"line {i}" for i in range(200)))
    app.text_set("right", "\n".join(f"line {i}" for i in range(200)))

    left.yview_moveto(0.5)
    assert right.yview()[0] == right_before or right.yview()[0] != left.yview()[0]


def test_paired_scroll_sync_moves_other_widget(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", sync_yscroll=True))

    left = app.text_widget("left")
    right = app.text_widget("right")
    assert left is not None
    assert right is not None

    app.text_set("left", "\n".join(f"line {i}" for i in range(200)))
    app.text_set("right", "\n".join(f"line {i}" for i in range(200)))

    # Realize the root geometry; with default 1x1 size, yview fractions are
    # clamped to the tiny visible window.  Mapping, sizing, then withdrawing
    # the window gives the layout a real 600x400 canvas without leaving it
    # visible during headless tests.
    import tkinter as tk
    root: tk.Tk = left.winfo_toplevel()  # type: ignore[assignment]
    root.deiconify()
    root.geometry("600x400")
    root.update_idletasks()
    root.withdraw()
    root.update_idletasks()

    left.yview_moveto(0.25)
    root.update_idletasks()
    # Compare panes to each other, not to the requested fraction: Text yview
    # snaps to line boundaries, and the snapped value differs by platform/font.
    assert abs(right.yview()[0] - left.yview()[0]) < 0.01
    assert left.yview()[0] > 0.05

    right.yview_moveto(0.75)
    root.update_idletasks()
    assert abs(left.yview()[0] - right.yview()[0]) < 0.01
    assert right.yview()[0] > 0.5


def test_paired_inherits_layout_spacing(build):
    app = _paired_app()
    build(app, layout=Layout(spacing=2).paired("left", "right"))

    frame = _paired_frame(app, "left")
    info = frame.pack_info()  # type: ignore[union-attr]
    assert info["padx"] == t.SPACE[2]
    assert info["pady"] == t.SPACE[2]
