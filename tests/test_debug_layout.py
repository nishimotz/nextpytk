"""Test debug_layout collects per-widget geometry/state."""
from __future__ import annotations

import pytest

from nextpytk import TkApp, Layout

from .conftest import requires_display

pytestmark = requires_display


def test_debug_layout_reports_widget_geometry(build):
    app = TkApp(title="debug")

    @app.label("msg")
    def msg():
        return "hello"

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=["msg", "go"])

    debug = app.debug_layout()
    assert debug["title"] == "debug"
    assert len(debug["sections"]) >= 1

    all_widgets = []
    for sec in debug["sections"]:
        all_widgets.extend(sec["widgets"])

    names = {w["name"] for w in all_widgets}
    assert "msg" in names
    assert "go" in names

    for w in all_widgets:
        assert "geometry" in w
        assert "reqwidth" in w
        assert "reqheight" in w
        assert "manager" in w
        assert "ismapped" in w


def test_debug_layout_button_meets_min_target(build):
    from nextpytk import tokens as t

    app = TkApp(title="debug")

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=["go"])

    debug = app.debug_layout()
    btn = next(
        w for sec in debug["sections"] for w in sec["widgets"] if w["name"] == "go"
    )
    assert btn["reqheight"] >= t.MIN_TARGET, f"{btn['reqheight']}px < {t.MIN_TARGET}px"
    assert btn["manager"] == "pack"
    assert btn["pack_info"]["side"] == "top"


def test_debug_layout_handles_grid_widgets(build):
    from nextpytk import Layout
    from nextpytk.types import Sticky

    app = TkApp(title="debug")

    @app.label("a")
    def a():
        return "A"

    @app.label("b")
    def b():
        return "B"

    build(
        app,
        layout=Layout()
        .grid()
        .widget("a", sticky=Sticky.NSEW)
        .widget("b", sticky=Sticky.NSEW)
        .end_grid(),
    )

    debug = app.debug_layout()
    widgets = [w for sec in debug["sections"] for w in sec["widgets"]]
    a_info = next(w for w in widgets if w["name"] == "a")
    b_info = next(w for w in widgets if w["name"] == "b")

    assert a_info["manager"] == "grid"
    assert a_info["grid_info"]["row"] == 0
    assert b_info["grid_info"]["row"] == 0
    assert a_info["grid_info"]["column"] == 0
    assert b_info["grid_info"]["column"] == 1


def test_debug_layout_regression_listbox_section_preserved(build):
    """Listbox callback changes must not alter the section geometry/manager.

    Regression guard for the index-based listbox callback refactor: if the
    listbox widget is accidentally rebuilt with a different master or manager,
    debug_layout catches it before the UI breaks.
    """
    app = TkApp(title="du-flat-regression")

    @app.label("path_lbl")
    def path_lbl():
        return "/"

    @app.listbox("file_list", items=["a", "b", "c"])
    def on_select(idx: int):
        return {}

    @app.button("up_btn", label="Up")
    def up_btn(vals: dict):
        return {}

    from nextpytk import Layout
    from nextpytk.types import Fill

    build(
        app,
        layout=Layout()
        .section("path_lbl")
        .section("file_list", fill=Fill.BOTH, expand=True)
        .section("up_btn"),
    )

    debug = app.debug_layout()
    widgets = [w for sec in debug["sections"] for w in sec["widgets"]]
    names = {w["name"]: w for w in widgets}

    file_list = names["file_list"]
    up_btn = names["up_btn"]

    assert file_list["manager"] == "pack"
    assert file_list["pack_info"]["fill"] == "both"
    assert bool(file_list["pack_info"]["expand"]) is True
    assert file_list["reqwidth"] > 0
    assert file_list["reqheight"] > 0

    assert up_btn["manager"] == "pack"
    assert up_btn["pack_info"]["fill"] in (None, "x", "both")
    assert bool(up_btn["pack_info"]["expand"]) is False
    assert up_btn["reqheight"] >= 44


def test_debug_layout_no_conflicts_when_single_manager(build):
    """A section whose widgets all share one manager reports no conflict."""
    from nextpytk import Layout

    app = TkApp(title="clean")

    @app.label("a")
    def a():
        return "A"

    @app.label("b")
    def b():
        return "B"

    build(
        app,
        layout=Layout().section("a").section("b"),
    )

    debug = app.debug_layout()
    assert debug["conflicts"] == []

    conflicts = app.check_layout_conflicts()
    assert conflicts == []


def test_debug_layout_detects_pack_place_conflict(build):
    """Mixing pack and place on the same master is reported as a conflict.

    Unlike pack/grid (which Tk rejects immediately at runtime), ``place`` may
    coexist with pack on one master, so the mixed state can actually exist.
    This is the case debug_layout is meant to surface.
    """
    import tkinter as tk

    from nextpytk import Layout

    app = TkApp(title="conflict")

    @app.label("packed")
    def packed():
        return "packed"

    build(
        app,
        layout=Layout().section("packed"),
    )

    # The section frame hosts "packed" (pack-managed). Place a second widget
    # into the same master with the place manager -- pack+place mix, which Tk
    # permits, so the conflicting state actually materializes.
    frame = app.layout_frame("packed")
    assert frame is not None

    from nextpytk import tokens as t

    manual = tk.Label(frame, text="manual", bg=t.BG)
    manual.place(x=5, y=5)

    debug = app.debug_layout()
    assert debug["conflicts"], "expected a pack/place conflict to be reported"
    conflict = debug["conflicts"][0]
    assert "place" in conflict["managers"]
    assert "pack" in conflict["managers"]
    assert "packed" in conflict["widgets"]
    assert "manual" in conflict["widgets"]


def test_check_layout_conflicts_warns_on_conflict(build):
    """check_layout_conflicts emits a UserWarning for each conflict."""
    import tkinter as tk
    import warnings

    from nextpytk import Layout

    app = TkApp(title="warn-conflict")

    @app.label("packed")
    def packed():
        return "packed"

    build(
        app,
        layout=Layout().section("packed"),
    )

    frame = app.layout_frame("packed")
    assert frame is not None

    from nextpytk import tokens as t

    tk.Label(frame, text="manual", bg=t.BG).place(x=5, y=5)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        conflicts = app.check_layout_conflicts()

    assert len(conflicts) == 1
    assert any("Conflicting geometry managers" in str(w.message) for w in caught)


def test_debug_layout_after_root_destroyed(harness, build):
    """debug_layout must not raise after the window is closed (root destroyed).

    Regression guard: calling ``debug_layout()`` after ``run()``/``mainloop``
    exits crashes with ``TclError: can't invoke "winfo" command: application
    has been destroyed`` because every widget (and the root) has been torn
    down. It should instead report ``alive=False`` and skip destroyed widgets.
    """
    app = TkApp(title="post-destroy")

    @app.label("msg")
    def msg():
        return "hello"

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(
        app,
        layout=["msg", "go"],
    )

    # Sanity: while live, it reports the widgets.
    debug = app.debug_layout()
    assert debug["alive"] is True
    names = {w["name"] for sec in debug["sections"] for w in sec["widgets"]}
    assert "msg" in names and "go" in names

    # Destroy the root, simulating the window being closed after run().
    harness.root.destroy()  # type: ignore[union-attr]
    harness.root = None
    app.clear_runtime()

    debug = app.debug_layout()  # must not raise
    assert debug["alive"] is False
    assert debug["sections"] == []
    assert debug["conflicts"] == []

    # check_layout_conflicts must also be safe after destruction.
    assert app.check_layout_conflicts() == []


def test_show_debug_padding_badges_padded_frames(build):
    """show_debug_padding badges every distinct section frame with padding."""
    from nextpytk import tokens as t

    app = TkApp(title="pad")

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=Layout()
          .section("go", padx=t.SPACE[2], pady=t.SPACE[3]))
    app.show_debug_padding(True)
    badges = app._debug_padding_badges
    # At least the explicit-padding section frame gets a badge.
    assert len(badges) >= 1
    texts = [b.cget("text") for b in badges]
    assert any("padx 8" in s for s in texts)  # SPACE[2] == 8
    assert any("pady 12" in s for s in texts)  # SPACE[3] == 12


def test_show_debug_padding_toggle_off_removes_badges(build):
    from nextpytk import tokens as t

    app = TkApp(title="pad")

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=Layout().section("go", padx=t.SPACE[2], pady=t.SPACE[2]))
    app.show_debug_padding(True)
    assert len(app._debug_padding_badges) >= 1
    app.show_debug_padding(False)
    assert app._debug_padding_badges == []


def test_widget_padding_reports_layout_padding(build):
    from nextpytk import tokens as t

    app = TkApp(title="pad")

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=Layout().section("go", padx=t.SPACE[2], pady=t.SPACE[2]))
    # Padding lives on the section frame, so the widget's own padding is 0.
    assert app.widget_padding("go") == {"padx": 0, "pady": 0}


def test_show_debug_padding_reports_inner_padding(build):
    """Label ``padding`` and text ``padx/pady`` are surfaced as inner badges."""
    app = TkApp(title="pad")

    @app.label("body", padding=(6, 10))
    def body():
        return "Body"

    @app.text(
        "code", readonly=True, wrap="none", height=4, width=40,
        widget_kwargs={"padx": 8, "pady": 12},
    )
    def code_content(value):
        return {}

    build(app, layout=Layout().section("body").section("code"))
    app.show_debug_padding(True)
    texts = [b.cget("text") for b in app._debug_padding_badges]
    assert any("inner padx (6, 10)" in s for s in texts)   # label padding
    assert any("inner padx 8 / pady 12" in s for s in texts)  # text padx/pady


def test_show_debug_padding_reports_self_padding(build):
    """A widget packed with explicit padx/pady gets a cyan self badge."""
    app = TkApp(title="pad")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))
    app.set_padding("body", padx=15, pady=20)
    app.show_debug_padding(True)
    texts = [b.cget("text") for b in app._debug_padding_badges]
    assert any("self padx 15 / pady 20" in s for s in texts)


def test_show_debug_padding_section_badge_lists_widgets(build):
    """A section badge reports which widget(s) its frame groups."""
    from nextpytk import tokens as t

    app = TkApp(title="pad")

    @app.label("title")
    def title():
        return "T"

    @app.label("body")
    def body():
        return "B"

    build(app, layout=Layout()
          .section("title", padx=t.SPACE[2], pady=t.SPACE[2])
          .section("body", "title", padx=t.SPACE[3]))
    app.show_debug_padding(True)
    texts = [b.cget("text") for b in app._debug_padding_badges]
    # The two-widget section frame reports the names it groups.
    assert any("section[" in s and "title" in s and "body" in s for s in texts)


def test_show_debug_padding_rebuilds_after_set_padding(build):
    """Rebuilding badges reflects a later set_padding change (resize use-case)."""
    app = TkApp(title="pad")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))
    app.show_debug_padding(True)
    texts = [b.cget("text") for b in app._debug_padding_badges]
    assert not any("self padx 15" in s for s in texts)

    # Change padding after the overlay is up, then rebuild (as <Configure> does).
    app.set_padding("body", padx=15, pady=20)
    app._build_padding_badges()
    texts = [b.cget("text") for b in app._debug_padding_badges]
    assert any("self padx 15 / pady 20" in s for s in texts)


def test_show_debug_padding_toggle_off_unbinds_resize(build):
    """show_debug_padding(False) removes the resize re-render binding."""
    app = TkApp(title="pad")

    @app.label("body")
    def body():
        return "Body"

    build(app, layout=Layout().section("body"))
    app.show_debug_padding(True)
    assert app._debug_padding_rebind is not None
    app.show_debug_padding(False)
    assert app._debug_padding_rebind is None


def test_show_debug_layout_badges_render_json_info(build):
    """show_debug_layout renders each widget's debug_layout() info at its spot."""
    app = TkApp(title="t")

    @app.label("title")
    def title():
        return "T"

    @app.button("go", label="Go")
    def go(vals):
        return {}

    build(app, layout=Layout().section("title").section("go"))
    app.show_debug_layout(True)
    badges = app._debug_layout_badges
    assert len(badges) == 2
    texts = [b.cget("text") for b in badges]
    assert any(s.startswith("title ") and "TLabel" in s for s in texts)
    assert any(s.startswith("go ") and "TButton" in s for s in texts)
    assert all("req " in s for s in texts)


def test_show_debug_layout_toggle_off(build):
    app = TkApp(title="t")

    @app.label("title")
    def title():
        return "T"

    build(app, layout=Layout().section("title"))
    app.show_debug_layout(True)
    assert len(app._debug_layout_badges) == 1
    assert app._debug_layout_rebind is not None
    app.show_debug_layout(False)
    assert app._debug_layout_badges == []
    assert app._debug_layout_rebind is None

