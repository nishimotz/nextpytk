"""Headless test fixtures for nextpytk.

``headless_app`` builds widgets into a withdrawn (never-mapped) Tk root and
drives callbacks programmatically -- no mainloop, no visible window.
Skips the whole session cleanly when no display is available (bare CI).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


def _ensure_tcl_env() -> None:
    """Point Tcl/Tk at the libraries bundled with uv-managed CPython.

    python-build-standalone compiles in a /tools/deps search path that does
    not exist on user machines (the "Can't find a usable init.tcl" failure
    noted in README).
    """
    import tkinter
    ver = f"{tkinter.TclVersion:.1f}"
    # uv-managed python-build-standalone stores Tcl/Tk under base_prefix/tcl/
    # rather than the standard lib/ layout.
    for prefix in (Path(sys.base_prefix) / "tcl", Path(sys.base_prefix) / "lib"):
        tcl_dir = prefix / f"tcl{ver}"
        tk_dir = prefix / f"tk{ver}"
        if (tcl_dir / "init.tcl").exists():
            os.environ["TCL_LIBRARY"] = str(tcl_dir)
        if tk_dir.exists():
            os.environ["TK_LIBRARY"] = str(tk_dir)


_ensure_tcl_env()

import tkinter as tk
from collections.abc import Callable, Iterator

import pytest

from nextpytk import TkApp


def _display_available() -> bool:
    """Check whether a display is available for Tk.

    Does **not** create a Tk instance.  On Python 3.14+freethreaded,
    creating a Tk, destroying it, then creating a second Tk and calling
    ``update_idletasks()`` reliably segfaults inside ``showRootWindow``.
    We avoid that by probing the environment instead of the interpreter.

    ``_ensure_tcl_env()`` (called at import time) already verified that the
    Tcl/Tk libraries are reachable; if they are not, ``tk.Tk()`` will raise
    ``TclError`` during ``_make_root()`` and the test will fail with a clear
    message.
    """
    if sys.platform == "darwin":
        return True  # macOS always has a window server
    if sys.platform == "win32":
        return True  # Windows always has a desktop
    # Linux / other Unix: check the usual display environment variables.
    return bool(
        os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
    )


requires_display = pytest.mark.skipif(
    not _display_available(), reason="no display available for Tk"
)


# Tk interpreter initialization reads many small Tcl files; under uv-managed
# python-build-standalone on Windows we occasionally see transient file-read
# failures when multiple roots are created in quick succession. Serializing
# root creation with a global lock prevents the races seen in the suite.
_tk_root_lock = threading.Lock()


class HeadlessHarness:
    """Build a TkApp against a withdrawn root and expose test helpers."""

    def __init__(self) -> None:
        self.root: tk.Tk | None = None

    @staticmethod
    def _make_root() -> tk.Tk:
        """Create a fresh Tk root with Tcl/Tk library paths refreshed.

        Retries a few times on transient Tcl file-read errors caused by
        concurrent library loading.
        """
        _ensure_tcl_env()
        with _tk_root_lock:
            for attempt in range(5):
                try:
                    return tk.Tk()
                except tk.TclError as exc:
                    # Windows + uv-managed Tcl sometimes fails to source a
                    # support file on the first attempt. Retry before giving up.
                    if attempt < 4:
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    raise
        raise tk.TclError("Failed to create Tk root")

    def build(self, app: TkApp, *, layout: object = None,
              initial_state: dict | None = None) -> TkApp:
        self.root = self._make_root()
        self.root.withdraw()
        app.set_root(self.root)
        app.clear_runtime()
        if layout is not None:
            from nextpytk.layout import Layout
            if isinstance(layout, list):
                layout = Layout.from_list(layout)
            layout.mount_frames(app)  # type: ignore[union-attr]
        app._build_swap_variants()  # mount swap-target variants (before widgets)
        app.build_widgets()
        if layout is not None:
            layout.pack_children(app)  # type: ignore[union-attr]
        app._pack_swap_variants()  # pack variant children + show default
        if initial_state:
            app._apply_initial_state(initial_state)  # same path as app.run()
        app.sync()
        return app

    def pump(self) -> None:
        """Process pending Tk events without entering mainloop."""
        assert self.root is not None
        try:
            while self.root.tk.dooneevent(0):
                pass
        except tk.TclError:
            return

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
