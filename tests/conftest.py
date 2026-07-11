"""Headless test fixtures for nextpytk.

``headless_app`` builds widgets into a withdrawn (never-mapped) Tk root and
drives callbacks programmatically -- no mainloop, no visible window.
Skips the whole session cleanly when no display is available (bare CI).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_tcl_env() -> None:
    """Point Tcl/Tk at the libraries bundled with uv-managed CPython.

    python-build-standalone compiles in a /tools/deps search path that does
    not exist on user machines (the "Can't find a usable init.tcl" failure
    noted in README).
    """
    if "TCL_LIBRARY" in os.environ:
        return
    import tkinter
    ver = f"{tkinter.TclVersion:.1f}"
    lib = Path(sys.base_prefix) / "lib"
    if (lib / f"tcl{ver}" / "init.tcl").exists():
        os.environ["TCL_LIBRARY"] = str(lib / f"tcl{ver}")
    if (lib / f"tk{ver}").exists():
        os.environ["TK_LIBRARY"] = str(lib / f"tk{ver}")


_ensure_tcl_env()

import tkinter as tk
from collections.abc import Callable, Iterator

import pytest

from nextpytk import TkApp


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


requires_display = pytest.mark.skipif(
    not _display_available(), reason="no display available for Tk"
)


class HeadlessHarness:
    """Build a TkApp against a withdrawn root and expose test helpers."""

    def __init__(self) -> None:
        self.root: tk.Tk | None = None

    def build(self, app: TkApp, *, layout: object = None,
              initial_state: dict | None = None) -> TkApp:
        self.root = tk.Tk()
        self.root.withdraw()
        app.set_root(self.root)
        app.clear_runtime()
        if layout is not None:
            from nextpytk.layout import Layout
            if isinstance(layout, list):
                layout = Layout.from_list(layout)
            layout.mount_frames(app)  # type: ignore[union-attr]
        app.build_widgets()
        if layout is not None:
            layout.pack_children(app)  # type: ignore[union-attr]
        if initial_state:
            app.apply_state(initial_state)
        app.sync()
        return app

    def pump(self) -> None:
        """Process pending Tk events without entering mainloop."""
        assert self.root is not None
        self.root.update()

    def press_key(self, sequence: str) -> None:
        """Fire a global key binding (as bind_all would receive it)."""
        assert self.root is not None
        self.root.event_generate(sequence)
        self.pump()

    def teardown(self) -> None:
        if self.root is not None:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None


@pytest.fixture
def harness() -> Iterator[HeadlessHarness]:
    h = HeadlessHarness()
    yield h
    h.teardown()


@pytest.fixture
def build(harness: HeadlessHarness) -> Callable[..., TkApp]:
    return harness.build
