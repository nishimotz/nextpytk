"""Text widget public API and state sync."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_text_widget_returns_real_tk_text(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])

    real = app.text_widget("body")
    assert isinstance(real, tk.Text)
    # app.widget returns the outer container frame, not the tk.Text.
    container = app.widget("body")
    assert isinstance(container, (tk.Frame, ttk.Frame))
    assert container is not real


def test_text_get_returns_contents(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    app.text_set("body", "hello world")
    assert app.text_get("body") == "hello world"


def test_apply_state_updates_text_widget(build):
    app = TkApp(title="t")

    @app.text("preview", readonly=True)
    def preview(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["preview"])
    app.apply_state({"preview": "line one\nline two"})
    assert app.text_get("preview") == "line one\nline two"


def test_text_widget_skips_update_when_unchanged(build):
    app = TkApp(title="t")

    @app.text("preview", readonly=True)
    def preview(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["preview"])
    app.text_set("preview", "same")
    real = app.text_widget("preview")
    assert real is not None
    real.mark_set("insert", "1.2")
    app.apply_state({"preview": "same"})
    # Cursor position should be preserved because no actual replacement happened.
    assert real.index("insert") == "1.2"


def test_text_widget_unknown_name_returns_none(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert app.text_widget("no-such-widget") is None
    assert app.text_get("no-such-widget") == ""


def test_on_text_change_receives_actual_text(build):
    """Regression: _on_text_change must read from the real tk.Text, not the container."""
    app = TkApp(title="t")
    received = []

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        received.append(value)
        return {}

    build(app, layout=["body"])
    app.text_set("body", "typed contents")

    spec = next(s for s in app._widgets if s.kind == "text")
    app._on_text_change(spec, body)

    assert received == ["typed contents"]


def test_text_wrap_defaults_to_word(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "word"


def test_text_wrap_none_logical_lines(build):
    app = TkApp(title="t")

    @app.text("body", wrap="none")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "none"


def test_text_h_scroll_adds_horizontal_scrollbar(build):
    app = TkApp(title="t")

    @app.text("body", wrap="none", h_scroll=True)
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("wrap") == "none"
    # A horizontal scrollbar was created and wired to the text xview.
    hsb = app._text_hscrollbars.get("body")
    assert hsb is not None
    assert real.cget("xscrollcommand")


def test_text_without_h_scroll_has_no_hscrollbar(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert "body" not in app._text_hscrollbars
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("xscrollcommand") == ""


def test_text_without_scrollbar_has_no_vscrollbar(build):
    app = TkApp(title="t")

    @app.text("body", scrollbar=False)
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert app._text_scrollbars.get("body") is None
    real = app.text_widget("body")
    assert real is not None
    # No vertical scrollbar wired up, so yscrollcommand stays empty.
    assert real.cget("yscrollcommand") == ""
    # The text itself is still built and usable.
    app.text_set("body", "line one\nline two")
    assert app.text_get("body") == "line one\nline two"


def test_text_scrollbar_defaults_to_present(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    assert app._text_scrollbars.get("body") is not None
    real = app.text_widget("body")
    assert real is not None
    assert real.cget("yscrollcommand")


def test_hide_removes_widget_and_show_restores_packed(build):
    app = TkApp(title="t")

    @app.label("note")
    def note():
        return "hi"

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["note", "body"])

    body_w = app.widget("body")
    note_w = app.widget("note")
    assert body_w is not None and note_w is not None
    assert app.is_visible("body")
    assert app.is_visible("note")

    app.hide("body")
    assert not app.is_visible("body")
    assert app.is_visible("note")  # sibling unaffected
    # Hidden widget is remembered so a later sync does not repack it.
    assert "body" in app._hidden_widgets
    app.sync()
    assert not app.is_visible("body")

    app.show("body")
    assert app.is_visible("body")
    assert "body" not in app._hidden_widgets
    # Grid/pack geometry preserved.
    assert body_w.winfo_manager() == "pack"


def test_hide_show_gridded_widget_preserves_cell(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    # Force the text onto the grid by re-packing it into a small grid cell.
    container = app.widget("body")
    assert container is not None
    container.grid_forget()
    container.grid(row=0, column=0, sticky="nsew")

    app.hide("body")
    assert not app.is_visible("body")
    app.show("body")
    assert app.is_visible("body")
    # grid_remove preserved the original cell.
    info = container.grid_info()
    assert info["row"] == 0
    assert info["column"] == 0


def test_hide_show_idempotent(build):
    app = TkApp(title="t")

    @app.label("note")
    def note():
        return "hi"

    build(app, layout=["note"])
    # Hiding an already-hidden widget is a no-op.
    app.hide("note")
    app.hide("note")
    assert not app.is_visible("note")
    # Showing an already-visible widget is a no-op.
    app.show("note")
    app.show("note")
    assert app.is_visible("note")


def test_set_padding_visible_applies_immediately(build):
    app = TkApp(title="t")

    @app.label("note")
    def note():
        return "hi"

    build(app, layout=["note"])

    w = app.widget("note")
    assert w is not None
    app.set_padding("note", padx=30)
    assert w.winfo_manager() == "pack"
    assert w.pack_info().get("padx") == 30


def test_set_padding_hidden_applies_on_show(build):
    """set_padding while hidden must not re-pack (re-show) the widget."""
    app = TkApp(title="t")

    @app.label("note")
    def note():
        return "hi"

    build(app, layout=["note"])
    w = app.widget("note")
    assert w is not None

    app.hide("note")
    assert not app.is_visible("note")

    # The bug: calling pack_configure on a pack_forget'd widget re-shows it.
    app.set_padding("note", padx=40)
    assert not app.is_visible("note"), "hidden widget must stay hidden"

    app.show("note")
    assert app.is_visible("note")
    assert w.pack_info().get("padx") == 40
    assert "note" not in app._hidden_padding


def test_set_padding_gridded(build):
    app = TkApp(title="t")

    @app.text("body")
    def body(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["body"])
    w = app.widget("body")
    assert w is not None
    w.grid_forget()
    w.grid(row=0, column=0, sticky="nsew")

    app.set_padding("body", padx=(5, 10), pady=3)
    info = w.grid_info()
    assert info["padx"] == (5, 10)
    assert info["pady"] == 3


def test_relax_minsize_lowers_min_to_requested(build):
    """A tiny app should not be stretched to the 380x260 default minimum."""
    app = TkApp(title="t")

    @app.button("hello")
    def on_hello():
        return "world"

    build(app, layout=["hello"])
    app._relax_minsize()
    root = app._root
    root.update_idletasks()
    req_w, req_h = root.winfo_reqwidth(), root.winfo_reqheight()
    min_w, min_h = root.wm_minsize()
    # Minimum must not exceed the requested size (it may be lowered to fit).
    assert min_w <= req_w
    assert min_h <= req_h


def test_relax_minsize_skips_when_explicit_geometry(build):
    """Explicit geometry must be respected; minsize stays at the default."""
    app = TkApp(title="t")

    @app.button("hello")
    def on_hello():
        return "world"

    build(app, layout=["hello"])
    root = app._root
    root.geometry("720x480")
    app._relax_minsize(explicit_geometry="720x480")
    root.update_idletasks()
    min_w, min_h = root.wm_minsize()
    assert (min_w, min_h) == (380, 260)

