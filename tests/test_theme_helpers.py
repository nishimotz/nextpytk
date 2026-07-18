# -*- coding: utf-8 -*-
"""Tests for Kizashi theme layout helpers in nextpytk.theme."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from nextpytk import apply_theme, content_frame, divider, field_row, heading, tokens as t

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


def test_heading_uses_tk_label_with_theme_bg(themed_root):
    """heading() uses tk.Label so its background matches the theme ground."""
    body = content_frame(themed_root)
    lbl = heading(body, "Title", scale="h3")
    assert isinstance(lbl, tk.Label)
    assert lbl.cget("bg") == t.BG
    assert lbl.cget("fg") == t.TEXT
    assert lbl.cget("font") != ""  # a font is assigned


def test_muted_heading_uses_muted_foreground(themed_root):
    body = content_frame(themed_root)
    lbl = heading(body, "Subtitle", muted=True)
    assert lbl.cget("fg") == t.TEXT_MUTED


def test_field_row_label_is_tk_label_with_theme_bg(themed_root):
    """field_row() labels are tk.Label with the theme background."""
    body = content_frame(themed_root)
    fields = tk.Frame(body, bg=t.BG)
    fields.pack()
    var = tk.StringVar()
    entry = field_row(fields, row=0, label_text="Name", textvariable=var)

    children = [c for c in fields.winfo_children() if isinstance(c, tk.Label)]
    assert len(children) == 1
    label = children[0]
    assert label.cget("bg") == t.BG
    assert label.cget("fg") == t.NEUTRAL[700]

    assert isinstance(entry, ttk.Entry)


def test_field_row_entry_font_and_spacing(themed_root):
    body = content_frame(themed_root)
    fields = tk.Frame(body, bg=t.BG)
    fields.pack()
    var = tk.StringVar(value="42")
    entry = field_row(fields, row=0, label_text="Value", textvariable=var)

    assert entry.cget("font") != ""  # a font is assigned
    info = fields.grid_columnconfigure(1)
    assert info["weight"] == 1  # type: ignore[index]
