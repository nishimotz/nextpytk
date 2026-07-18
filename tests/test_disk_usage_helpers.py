"""Tests for disk-usage layout helpers in nextpytk.theme."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from nextpytk import (
    add_row,
    apply_theme,
    button,
    clear_rows,
    content_frame,
    data_list,
    status_bar,
    window_header,
    tokens as t,
)

from .conftest import requires_display, HeadlessHarness

pytestmark = requires_display


@pytest.fixture
def themed_root():
    root = HeadlessHarness._make_root()
    root.withdraw()
    apply_theme(root)
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_window_header_returns_labels_and_rule(themed_root):
    body = content_frame(themed_root)
    title_lbl, sub_lbl = window_header(body, "Title", "Subtitle")
    assert isinstance(title_lbl, tk.Label)
    assert title_lbl.cget("text") == "Title"
    assert isinstance(sub_lbl, tk.Label)
    assert sub_lbl.cget("text") == "Subtitle"
    assert sub_lbl.cget("fg") == t.TEXT_MUTED


def test_data_list_builds_treeview_with_columns(themed_root):
    body = content_frame(themed_root)
    container, tree = data_list(
        body,
        columns=[
            ("size", "Size", 80, "e"),
            ("name", "Name", None, "w"),
        ],
        height=8,
    )
    assert isinstance(container, ttk.Frame)
    assert isinstance(tree, ttk.Treeview)
    assert tree["columns"] == ("size", "name")
    assert tree.set("", "size") == ""  # no rows yet


def test_add_row_zebra_striping(themed_root):
    body = content_frame(themed_root)
    _, tree = data_list(body, columns=[("a", "A", 40, "w")])
    add_row(tree, ("first",))
    add_row(tree, ("second",))
    items = tree.get_children()
    assert tree.item(items[0], "tags") == ("even",)
    assert tree.item(items[1], "tags") == ("odd",)


def test_clear_rows_removes_all(themed_root):
    body = content_frame(themed_root)
    _, tree = data_list(body, columns=[("a", "A", 40, "w")])
    add_row(tree, ("x",))
    add_row(tree, ("y",))
    clear_rows(tree)
    assert tree.get_children() == ()


def test_status_bar_status_label(themed_root):
    body = content_frame(themed_root)
    body.pack()  # make body a valid parent; status_bar uses side="bottom" on its own
    status_var = tk.StringVar(value="ready")
    lbl = status_bar(themed_root, textvariable=status_var)
    assert lbl.cget("text") == "ready"
    assert lbl.cget("fg") == t.TEXT_MUTED


def test_button_styles(themed_root):
    primary = button(themed_root, "Primary", primary=True)
    secondary = button(themed_root, "Secondary", primary=False)
    assert primary.cget("style") == "Primary.TButton"
    assert secondary.cget("style") == "Secondary.TButton"
