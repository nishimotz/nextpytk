"""Tests for GridBuilder.cell(), cell_raw(), and deprecation of GridBuilder.widget()."""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import warnings

import pytest

from nextpytk import Layout, LayoutBuilder
from .conftest import requires_display


def _grid_cells(builder) -> dict:
    """Return the cells dict from a _GridBuilder or the Layout it produced."""
    block = builder._block if hasattr(builder, "_block") else builder._blocks[-1]
    return block.cells


def _grid_raw_cells(builder) -> list:
    """Return the raw_cells list from a _GridBuilder or the Layout it produced."""
    block = builder._block if hasattr(builder, "_block") else builder._blocks[-1]
    return block.raw_cells


def test_cell_single_is_warning_free():
    """cell('a') must be warning-free and place the widget at column 0."""
    layout = Layout().grid()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        layout.cell("a").end_grid()
    assert not w
    assert set(_grid_cells(layout)) == {"a"}


def test_cell_multiple_place_horizontally():
    """cell('a', 'b', 'c') places widgets in consecutive columns, same row."""
    layout = Layout().grid().cell("a", "b", "c").end_grid()
    cells = _grid_cells(layout)
    assert cells["a"]["row"] == 0 and cells["a"]["column"] == 0
    assert cells["b"]["row"] == 0 and cells["b"]["column"] == 1
    assert cells["c"]["row"] == 0 and cells["c"]["column"] == 2


def test_cell_multiple_shared_options():
    """Options like sticky/padx/pady are shared across all cells."""
    layout = Layout().grid().cell("a", "b", sticky="ew", padx=5, pady=3).end_grid()
    for name in ("a", "b"):
        opts = _grid_cells(layout)[name]
        assert opts["sticky"] == "ew"
        assert opts["padx"] == 5
        assert opts["pady"] == 3


def test_cell_multiple_advances_cursor_for_next_call():
    """After cell('a', 'b'), the next cell starts at column 2."""
    layout = Layout().grid().cell("a", "b").cell("c").end_grid()
    cells = _grid_cells(layout)
    assert cells["c"]["column"] == 2


def test_cell_multiple_after_next_row():
    """cell('a', 'b') on row 1 places both cells on that row."""
    layout = Layout().grid().cell("x").next_row().cell("a", "b").end_grid()
    cells = _grid_cells(layout)
    assert cells["a"]["row"] == 1 and cells["a"]["column"] == 0
    assert cells["b"]["row"] == 1 and cells["b"]["column"] == 1


def test_cell_multiple_rejects_colspan():
    with pytest.raises(ValueError, match="does not support colspan/rowspan"):
        Layout().grid().cell("a", "b", colspan=2).end_grid()


def test_cell_multiple_rejects_rowspan():
    with pytest.raises(ValueError, match="does not support colspan/rowspan"):
        Layout().grid().cell("a", "b", rowspan=2).end_grid()


def test_cell_multiple_rejects_span_preset():
    with pytest.raises(ValueError, match="does not support colspan/rowspan"):
        Layout().grid().span(2).cell("a", "b").end_grid()


def test_cell_single_supports_colspan():
    """A single name still supports colspan (incl. the .span() preset)."""
    layout = Layout().grid().cell("a", colspan=2).end_grid()
    assert _grid_cells(layout)["a"]["columnspan"] == 2

    layout = Layout().grid().span(2).cell("a").end_grid()
    assert _grid_cells(layout)["a"]["columnspan"] == 2


def test_widget_is_deprecated_but_still_works():
    """widget() must emit DeprecationWarning yet place the widget."""
    with pytest.warns(DeprecationWarning, match=r"widget\(\) is deprecated"):
        layout = Layout().grid().widget("a").end_grid()
    assert set(_grid_cells(layout)) == {"a"}


def test_cell_equals_widget_for_single_name():
    """cell('a', sticky='ew') and widget('a', sticky='ew') produce identical cells."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        w_layout = Layout().grid().widget("a", sticky="ew").end_grid()
    c_layout = Layout().grid().cell("a", sticky="ew").end_grid()
    assert _grid_cells(c_layout) == _grid_cells(w_layout)


# ── cell_raw tests ──
# These create real tkinter widgets and need a display + a proper Tk root.
# We use the harness fixture to manage the Tk lifecycle cleanly.

@requires_display
def test_cell_raw_stores_widget_and_opts(harness):
    """cell_raw() stores the widget instance and grid options in raw_cells."""
    root = harness._make_root()
    try:
        w = ttk.Frame(root)
        layout = Layout().grid().cell_raw(w, sticky="nsew", rowspan=3).end_grid()
        raw = _grid_raw_cells(layout)
        assert len(raw) == 1
        stored_w, opts = raw[0]
        assert stored_w is w
        assert opts["row"] == 0
        assert opts["column"] == 0
        assert opts["sticky"] == "nsew"
        assert opts["rowspan"] == 3
    finally:
        root.destroy()


@requires_display
def test_cell_raw_advances_cursor(harness):
    """cell_raw() advances the column cursor like cell()."""
    root = harness._make_root()
    try:
        w1 = ttk.Frame(root)
        w2 = ttk.Frame(root)
        layout = Layout().grid().cell_raw(w1).cell_raw(w2).end_grid()
        raw = _grid_raw_cells(layout)
        assert raw[0][1]["column"] == 0
        assert raw[1][1]["column"] == 1
    finally:
        root.destroy()


@requires_display
def test_cell_raw_supports_colspan(harness):
    """cell_raw() supports colspan."""
    root = harness._make_root()
    try:
        w = ttk.Frame(root)
        layout = Layout().grid().cell_raw(w, colspan=2).end_grid()
        assert _grid_raw_cells(layout)[0][1]["columnspan"] == 2
    finally:
        root.destroy()


@requires_display
def test_cell_raw_supports_span_preset(harness):
    """cell_raw() respects the .span() preset."""
    root = harness._make_root()
    try:
        w = ttk.Frame(root)
        layout = Layout().grid().span(2).cell_raw(w).end_grid()
        assert _grid_raw_cells(layout)[0][1]["columnspan"] == 2
    finally:
        root.destroy()


@requires_display
def test_cell_raw_mixed_with_cell(harness):
    """cell_raw() and cell() can be mixed in the same grid."""
    root = harness._make_root()
    try:
        w = ttk.Frame(root)
        layout = Layout().grid().cell("a").cell_raw(w).cell("b").end_grid()
        cells = _grid_cells(layout)
        raw = _grid_raw_cells(layout)
        assert cells["a"]["column"] == 0
        assert raw[0][1]["column"] == 1
        assert cells["b"]["column"] == 2
    finally:
        root.destroy()


def test_layout_builder_cell_multiple():
    """LayoutBuilder.cell('a', 'b') places both widgets in consecutive cells."""
    builder = LayoutBuilder()
    with builder:
        with builder.grid():
            builder.cell("a", "b", sticky="ew")
    cells = _grid_cells(builder.build())
    assert cells["a"]["column"] == 0
    assert cells["b"]["column"] == 1
    assert cells["a"]["sticky"] == "ew"
    assert cells["b"]["sticky"] == "ew"


def test_layout_builder_cell_rejects_span():
    """LayoutBuilder.cell('a', 'b') with a pending span raises ValueError."""
    builder = LayoutBuilder()
    with builder:
        with builder.grid():
            builder.span(2)
            with pytest.raises(ValueError, match="does not support colspan/rowspan"):
                builder.cell("a", "b")


def test_layout_builder_widget_is_deprecated():
    """LayoutBuilder.widget() must emit DeprecationWarning yet still work."""
    builder = LayoutBuilder()
    with builder:
        with builder.grid():
            with pytest.warns(DeprecationWarning, match=r"widget\(\) is deprecated"):
                builder.widget("a")
    assert set(_grid_cells(builder.build())) == {"a"}
