"""Deprecation tests for plural grid weight/min-size helpers."""

from __future__ import annotations

import warnings

import pytest

from nextpytk import Layout, LayoutBuilder


@pytest.mark.parametrize("method", ["col_weights", "row_weights", "col_minsizes", "row_minsizes"])
def test_plural_grid_methods_emit_deprecation_warning(method):
    """Plural bulk methods must warn and still update the same grid config as singular calls."""
    layout = Layout().grid()
    block = layout._block

    with pytest.warns(DeprecationWarning, match=rf"{method}\(\) is deprecated"):
        getattr(layout, method)(0, 1)

    target_map = {
        "col_weights": "col_weights",
        "row_weights": "row_weights",
        "col_minsizes": "col_minsize",
        "row_minsizes": "row_minsize",
    }
    target = target_map[method]
    assert getattr(block, target) == {0: 0, 1: 1}


def test_layout_builder_grid_kwargs_emit_deprecation_warning():
    """LayoutBuilder.grid(col_weights=...) and grid(row_weights=...) must warn."""
    builder = LayoutBuilder()
    with pytest.warns(DeprecationWarning, match="col_weights=... is deprecated"):
        with builder.grid(col_weights=(0, 1)):
            pass

    builder2 = LayoutBuilder()
    with pytest.warns(DeprecationWarning, match="row_weights=... is deprecated"):
        with builder2.grid(row_weights=(1, 0)):
            pass

    assert builder._layout._blocks[-1].col_weights == {0: 0, 1: 1}
    assert builder2._layout._blocks[-1].row_weights == {0: 1, 1: 0}


def test_singular_equivalent_does_not_warn():
    """The recommended singular API stays warning-free."""
    layout = Layout().grid()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        layout.col_weight(0, 0).col_weight(1, 1)
        layout.row_weight(0, 0).row_weight(1, 1)
        layout.col_minsize(0, 10).col_minsize(1, 20)
        layout.row_minsize(0, 5).row_minsize(1, 15)
    assert not w
