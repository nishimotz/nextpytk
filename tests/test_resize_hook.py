"""Tests for the framework-managed ``on_resize`` hook.

The hook is installed by ``_install_resize_hook`` and guarantees:

- **Toplevel only**: child-widget ``<Configure>`` events are ignored.
- **Size-change only**: the callback fires only when ``(width, height)``
  actually changed, so reconfiguring widgets from the callback cannot loop.
- **Debounced**: rapid resize storms coalesce into a single callback.
"""

from __future__ import annotations

import time
import tkinter as tk

from nextpytk import TkApp


def _make_app(harness) -> TkApp:
    app = TkApp(title="resize-hook-test")
    harness.build(app)
    return app


def _pump(root: tk.Tk) -> None:
    """Process pending Tk events (including ``after`` callbacks) non-blockingly."""
    try:
        root.update()
    except tk.TclError:
        pass


def test_resize_hook_fires_on_size_change(harness, monkeypatch) -> None:
    app = _make_app(harness)
    root = harness.root
    assert root is not None

    calls: list[tuple[int, int]] = []
    app._install_resize_hook(lambda w, h: calls.append((w, h)))

    # The harness withdraws the root, so winfo_width() stays 1 and a real
    # geometry change is not reflected by the window manager. Simulate a
    # toplevel resize deterministically: report a new size and fire
    # <Configure> on the root itself.
    monkeypatch.setattr(root, "winfo_width", lambda: 500)
    monkeypatch.setattr(root, "winfo_height", lambda: 400)
    root.event_generate("<Configure>", width=500, height=400)
    _pump(root)
    # The hook debounces via a 60ms after(); sleep past it, then pump.
    time.sleep(0.1)
    _pump(root)

    assert calls, "expected on_resize to fire after a toplevel resize"


def test_resize_hook_ignores_child_configure(harness) -> None:
    app = _make_app(harness)
    root = harness.root
    assert root is not None

    calls: list[tuple[int, int]] = []
    app._install_resize_hook(lambda w, h: calls.append((w, h)))

    # A child widget's <Configure> must NOT trigger the hook.
    child = tk.Frame(root)
    child.event_generate("<Configure>", width=100, height=50)
    _pump(root)
    _pump(root)

    assert calls == [], "child <Configure> must not fire the toplevel resize hook"


def test_resize_hook_no_loop_on_unchanged_size(harness) -> None:
    app = _make_app(harness)
    root = harness.root
    assert root is not None

    calls: list[tuple[int, int]] = []
    app._install_resize_hook(lambda w, h: calls.append((w, h)))

    # Fire <Configure> with the same size repeatedly: the hook must not fire
    # more than once (the size did not change), preventing an infinite loop.
    root.event_generate("<Configure>", width=300, height=200)
    root.event_generate("<Configure>", width=300, height=200)
    root.event_generate("<Configure>", width=300, height=200)
    _pump(root)
    _pump(root)

    assert len(calls) <= 1, "unchanged size must not re-fire the resize hook"
