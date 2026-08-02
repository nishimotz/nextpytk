"""Tests for dynamic layout switching via Layout.target + @app.swap."""

from __future__ import annotations

from nextpytk import Layout, TkApp

from .conftest import requires_display

pytestmark = requires_display


def _swap_app() -> TkApp:
    app = TkApp(title="t")

    @app.swap(
        "main",
        variants={
            "dir":  [Layout().section("tree")],
            "file": [Layout().paired("left", "right")],
        },
        default="dir",
    )
    def main():
        return {}

    @app.treeview("tree", columns=[("name", "Name")])
    def tree(idx):
        return {}

    @app.text("left", readonly=True)
    def left(value):
        return {}

    @app.text("right", readonly=True)
    def right(value):
        return {}

    return app


def test_swap_registers_variants():
    app = _swap_app()
    cfg = app._swap_variants["main"]
    assert set(cfg["variants"].keys()) == {"dir", "file"}
    assert cfg["default"] == "dir"


def _is_shown(frame):
    """Whether a variant frame is packed (visible) vs packed-forget (hidden).

    ``winfo_ismapped()`` returns False under a withdrawn root, so we instead
    check the pack geometry manager state: a packed frame has ``pack_info()``,
    a ``pack_forget`` one raises TclError.
    """
    try:
        frame.pack_info()  # type: ignore[union-attr]
        return True
    except Exception:
        return False


def test_swap_builds_variant_frames(build):
    app = _swap_app()
    build(app, layout=Layout().target("main"))

    # The target frame exists and holds variant sub-frames.
    target = app._swap_targets.get("main")
    assert target is not None
    assert "dir" in app._swap_frames["main"]
    assert "file" in app._swap_frames["main"]

    # Default variant is shown, the other is hidden.
    dir_frame = app._swap_frames["main"]["dir"]
    file_frame = app._swap_frames["main"]["file"]
    assert _is_shown(dir_frame)
    assert not _is_shown(file_frame)


def test_swap_switches_variant(build):
    app = _swap_app()
    build(app, layout=Layout().target("main"))

    app.swap_view("main", "file")
    dir_frame = app._swap_frames["main"]["dir"]
    file_frame = app._swap_frames["main"]["file"]
    assert not _is_shown(dir_frame)
    assert _is_shown(file_frame)
    assert app._swap_current["main"] == "file"


def test_swap_back_and_forth_preserves_geometry(build):
    app = _swap_app()
    build(app, layout=Layout().target("main"))

    app.swap_view("main", "file")
    app.swap_view("main", "dir")
    dir_frame = app._swap_frames["main"]["dir"]
    file_frame = app._swap_frames["main"]["file"]
    assert _is_shown(dir_frame)
    assert not _is_shown(file_frame)


def test_swap_default_from_initial_state(build):
    """swap_view before build records intent; build shows the default."""
    app = _swap_app()
    app.swap_view("main", "file")
    build(app, layout=Layout().target("main"))
    # After build the default (dir) wins, since swap_view ran pre-mount.
    dir_frame = app._swap_frames["main"]["dir"]
    file_frame = app._swap_frames["main"]["file"]
    assert _is_shown(dir_frame)
    assert not _is_shown(file_frame)
