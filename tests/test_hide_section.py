"""Tests for Layout.section(name=) and app.hide_section()/show_section()."""
from __future__ import annotations

import pytest

from nextpytk import TkApp, Layout

from .conftest import requires_display

pytestmark = requires_display


def _section_frame(app: TkApp, name: str):
    w = app.widget(name)
    assert w is not None
    return w.master  # type: ignore[no-any-return]


def test_section_name_registers_section_frame(build):
    """An explicit section(name=) is registered under that exact name."""
    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body", name="main_body"))

    assert "main_body" in app._section_frames
    # The frame wraps the body widget.
    assert app._section_frames["main_body"] is _section_frame(app, "body")
    # Explicit names are tracked so the badge uses them.
    assert "main_body" in app._explicit_section_names


def test_section_without_name_derives_first_widget_section(build):
    """Omitting name= registers the frame as '<first widget>_section'."""
    app = TkApp(title="t")

    @app.label("diagram")
    def diagram():
        return "Diagram"

    @app.label("code")
    def code():
        return "Code"

    build(app, layout=Layout().section("diagram", "code"))

    assert "diagram_section" in app._section_frames
    assert "diagram_section" not in app._explicit_section_names
    # The auto-derived key maps to the section frame hosting the widgets.
    assert app._section_frames["diagram_section"] is _section_frame(app, "diagram")
    assert app._section_frames["diagram_section"] is _section_frame(app, "code")


def test_hide_section_removes_and_show_restores_frame(build):
    """hide_section unpacks the section frame; show_section re-packs it."""
    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))

    frame = _section_frame(app, "body")
    assert frame.winfo_manager() == "pack"

    app.hide_section("body_section")
    assert frame.winfo_manager() == ""

    app.show_section("body_section")
    assert frame.winfo_manager() == "pack"


def test_hide_section_preserves_pack_options(build):
    """show_section restores side/fill/expand/padx/pady from hide time."""
    from nextpytk import tokens as t

    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section(
        "body", fill="both", expand=True, padx=t.SPACE[2], pady=t.SPACE[2]))

    frame = _section_frame(app, "body")
    before = {k: v for k, v in frame.pack_info().items()}

    app.hide_section("body_section")
    app.show_section("body_section")

    after = frame.pack_info()
    assert frame.winfo_manager() == "pack"
    # side/fill/expand survive the round-trip.
    assert after.get("side") == before.get("side")
    assert after.get("fill") == before.get("fill")
    assert after.get("expand") == before.get("expand")
    # Numeric padding survives the round-trip too.
    assert after.get("padx") == before.get("padx")
    assert after.get("pady") == before.get("pady")


def test_hide_section_twice_is_noop(build):
    """Calling hide_section on an already-hidden section is harmless."""
    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))

    frame = _section_frame(app, "body")
    app.hide_section("body_section")
    app.hide_section("body_section")  # must not raise or double-save
    assert frame.winfo_manager() == ""

    # Restoring still works after the repeated hide.
    app.show_section("body_section")
    assert frame.winfo_manager() == "pack"


def test_show_section_without_hide_is_noop(build):
    """show_section on a visible section is a no-op, not an error."""
    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))

    frame = _section_frame(app, "body")
    assert frame.winfo_manager() == "pack"
    app.show_section("body_section")
    assert frame.winfo_manager() == "pack"


def test_hide_section_unknown_name_is_noop(build):
    """hide_section/show_section with an unknown name must not raise."""
    app = TkApp(title="t")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))
    # No registered section named "nope".
    app.hide_section("nope")
    app.show_section("nope")


def test_hide_section_leaves_sibling_section_mapped(build):
    """Hiding one section must not affect an unrelated section's frame."""
    app = TkApp(title="t")

    @app.label("title")
    def title():
        return "Title"

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("title").section("body"))

    title_frame = _section_frame(app, "title")
    body_frame = _section_frame(app, "body")
    assert title_frame.winfo_manager() == "pack"
    assert body_frame.winfo_manager() == "pack"

    app.hide_section("body_section")
    assert body_frame.winfo_manager() == ""
    assert title_frame.winfo_manager() == "pack"

    app.show_section("body_section")
    assert body_frame.winfo_manager() == "pack"
