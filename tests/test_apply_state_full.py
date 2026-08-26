"""Tests for apply_state(full=...): partial vs full sync semantics."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_apply_state_full_false_updates_state(build):
    app = TkApp(title="t")

    app.add_label("a", text="")
    app.add_label("b", text="")

    build(app, layout=["a", "b"])

    app.apply_state({"a": 1, "b": 2}, full=False)
    assert app.state["a"] == 1
    assert app.state["b"] == 2


def test_apply_state_partial_only_syncs_touched_keys(build):
    """full=False should only resync widgets whose keys actually changed."""
    app = TkApp(title="t")
    app.add_label("a", text="")
    app.add_label("b", text="")
    build(app, layout=["a", "b"])

    sync_keys: list[set[str]] = []
    orig = TkApp._sync_widgets_for_keys

    def spy(self, update):
        sync_keys.append(set(update))
        return orig(self, update)

    # Apply a change to only "a".
    with patch.object(TkApp, "_sync_widgets_for_keys", spy):
        app.apply_state({"a": "x"}, full=False)

    # The partial sync path is used (full=True would call _sync_widgets instead).
    assert sync_keys and sync_keys[-1] == {"a"}


def test_apply_state_full_default_is_full(build):
    """Default full=True should use the full widget sweep (_sync_widgets)."""
    app = TkApp(title="t")
    app.add_label("a", text="")
    build(app, layout=["a"])

    full_called: list[bool] = []
    orig_full = TkApp._sync_widgets
    orig_partial = TkApp._sync_widgets_for_keys

    def spy_full(self):
        full_called.append(True)
        return orig_full(self)

    def spy_partial(self, update):
        full_called.append(False)
        return orig_partial(self, update)

    with patch.object(TkApp, "_sync_widgets", spy_full), \
         patch.object(TkApp, "_sync_widgets_for_keys", spy_partial):
        app.apply_state({"a": "y"})

    assert full_called and full_called[0] is True


def test_apply_state_full_false_noop_is_skipped(build):
    """full=False filters no-op values before partial sync."""
    app = TkApp(title="t")
    calls: list[str] = []

    orig = TkApp._sync_widgets_for_keys

    def spy(self, update):
        calls.append(f"sync:{update}")
        return orig(self, update)

    build(app, layout=["x"])
    # Establish state "x" = "seed" through apply_state so the value is real.
    app.apply_state({"x": "seed"}, full=False)

    with patch.object(TkApp, "_sync_widgets_for_keys", spy):
        app.apply_state({"x": "seed"}, full=False)  # no-op vs current

    assert calls and calls[-1] == "sync:{}"  # empty update → fast skip


def test_apply_state_full_false_real_change_is_synced(build):
    """full=False still syncs keys whose value actually changed."""
    app = TkApp(title="t")
    app.add_label("x", text="")
    build(app, layout=["x"])

    sync_keys: list[set[str]] = []
    orig = TkApp._sync_widgets_for_keys

    def spy(self, update):
        sync_keys.append(set(update))
        return orig(self, update)

    with patch.object(TkApp, "_sync_widgets_for_keys", spy):
        app.apply_state({"x": "changed"}, full=False)

    assert sync_keys and sync_keys[-1] == {"x"}


def test_apply_state_full_false_with_untracked(build):
    app = TkApp(title="t")
    app.add_label("status", text="")
    build(app, layout=["status"])

    with app.untracked():
        app.apply_state({"status": "b"}, full=False)
    assert app.state["status"] == "b"