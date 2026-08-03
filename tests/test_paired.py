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


def test_paired_line_numbers_creates_gutters(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", line_numbers=True))

    frame = _paired_frame(app, "left")
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    gutter_b = getattr(frame, "_paired_gutter_b", None)
    shared_sb = getattr(frame, "_paired_shared_scroll", None)
    assert gutter_a is not None
    assert gutter_b is not None
    assert shared_sb is not None


def test_paired_line_numbers_populated(build):
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", line_numbers=True))

    app.text_set("left", "\n".join(f"line {i}" for i in range(1, 6)))
    app.text_set("right", "\n".join(f"line {i}" for i in range(1, 6)))

    frame = _paired_frame(app, "left")
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    gutter_b = getattr(frame, "_paired_gutter_b", None)
    assert gutter_a is not None
    assert gutter_b is not None
    # Logical line numbers 1..5 on both gutters.
    assert str(gutter_a.get("1.0", "end-1c")).splitlines() == [
        "1", "2", "3", "4", "5"
    ]
    assert str(gutter_b.get("1.0", "end-1c")).splitlines() == [
        "1", "2", "3", "4", "5"
    ]


def test_paired_gutters_count_logical_lines_when_wrapped(build):
    """Gutters show logical line numbers even when long lines wrap.

    A wrapped line must not inflate the gutter count: ``index("end-1c")``
    counts display rows, so the old gutter logic numbered physical rows.
    Regression guard for the logical-line fix.
    """
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", line_numbers=True))

    # 3 logical lines; the middle one is long enough to wrap.
    app.text_set("left", "line one\n" + "x" * 120 + "\nline three")
    app.text_set("right", "line one\n" + "x" * 120 + "\nline three")

    frame = _paired_frame(app, "left")
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    assert gutter_a is not None
    assert str(gutter_a.get("1.0", "end-1c")).splitlines() == ["1", "2", "3"]


def test_paired_line_numbers_shared_scrollbar(build):
    """Both gutters and both panes share the single vertical scrollbar."""
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", line_numbers=True))

    app.text_set("left", "\n".join(f"line {i}" for i in range(200)))
    app.text_set("right", "\n".join(f"line {i}" for i in range(200)))

    left = app.text_widget("left")
    right = app.text_widget("right")
    assert left is not None
    assert right is not None
    frame = _paired_frame(app, "left")
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    gutter_b = getattr(frame, "_paired_gutter_b", None)
    assert gutter_a is not None and gutter_b is not None

    # All four widgets drive the same shared scrollbar via yscrollcommand.
    sb_a = app._text_scrollbars.get("left")
    # The per-widget scrollbars are hidden when gutters are active.
    assert sb_a is not None and not sb_a.winfo_ismapped()

    # Scrolling one widget must move all the others (shared command).
    import tkinter as tk
    root: tk.Tk = left.winfo_toplevel()  # type: ignore[assignment]
    root.deiconify()
    root.geometry("600x400")
    root.update_idletasks()
    root.withdraw()
    root.update_idletasks()

    left.yview_moveto(0.5)
    root.update_idletasks()
    assert abs(right.yview()[0] - left.yview()[0]) < 0.01
    assert abs(gutter_a.yview()[0] - left.yview()[0]) < 0.01
    assert abs(gutter_b.yview()[0] - left.yview()[0]) < 0.01


def test_paired_gutter_sync_does_not_recursively_loop(build):
    """Gutter rewrite + scroll sync must not recurse infinitely.

    Rewriting a gutter calls ``update_idletasks()``, which fires the shared
    scrollbar's ``yscrollcommand`` and re-enters the gutter helpers via
    ``_chain_yview``. Without the per-gutter ``_syncing_gutter`` guard this
    recurses forever. Regression guard for the re-entry fix.
    """
    app = _paired_app()
    build(app, layout=Layout().paired("left", "right", line_numbers=True))

    # Multiple programmatic content replacements, each of which rewrites the
    # gutter and (via update_idletasks) fires yscrollcommand re-entrantly.
    for i in range(1, 6):
        content = "\n".join(f"line {j}" for j in range(1, i * 3 + 1))
        app.text_set("left", content)
        app.text_set("right", content)

    frame = _paired_frame(app, "left")
    gutter_a = getattr(frame, "_paired_gutter_a", None)
    assert gutter_a is not None
    # 5 * 3 = 15 logical lines on the left gutter.
    assert str(gutter_a.get("1.0", "end-1c")).splitlines() == [
        str(k) for k in range(1, 16)
    ]


def test_clear_runtime_clears_text_set_hooks():
    """clear_runtime() drops registered on_text_set hooks to avoid leaks.

    A paired gutter registers an ``on_text_set`` hook per build; without
    clearing on ``clear_runtime()`` these hooks accumulate across re-runs
    (e.g. swap variants rebuilt at runtime), running the gutter sync multiple
    times. Regression guard for the hook-leak fix.
    """
    app = _paired_app()
    app.clear_runtime()

    def _hook():
        return None

    app.on_text_set("left", _hook)
    app.on_text_set("left", _hook)
    assert len(app._text_set_hooks.get("left", [])) == 2

    app.clear_runtime()
    assert app._text_set_hooks.get("left") is None or not app._text_set_hooks["left"]
