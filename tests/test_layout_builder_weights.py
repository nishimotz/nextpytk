"""Tests for LayoutBuilder delegation of grid configuration methods (col_weight, row_weight, etc.)."""

from __future__ import annotations

from nextpytk import LayoutBuilder
from nextpytk.layout import _Grid


def test_layout_builder_col_and_row_weights():
    """LayoutBuilder should delegate col_weight and row_weight chaining inside grid()."""
    builder = LayoutBuilder()
    with builder:
        with builder.grid():
            builder.col_weight(0, 1).col_weight(1, 3)
            builder.row_weight(0, 2).row_weight(1, 4)
            builder.cell("a", "b")
            builder.next_row()
            builder.cell("c", "d")

    layout = builder.build()
    block = layout._blocks[0]
    assert isinstance(block, _Grid)
    assert block.col_weights == {0: 1, 1: 3}
    assert block.row_weights == {0: 2, 1: 4}


def test_layout_builder_col_and_row_minsizes():
    """LayoutBuilder should delegate col_minsize and row_minsize inside grid()."""
    builder = LayoutBuilder()
    with builder:
        with builder.grid():
            builder.col_minsize(0, 100).col_minsize(1, 200)
            builder.row_minsize(0, 50)
            builder.cell("x")

    layout = builder.build()
    block = layout._blocks[0]
    assert isinstance(block, _Grid)
    assert block.col_minsize == {0: 100, 1: 200}
    assert block.row_minsize == {0: 50}
