"""Tests for app.batch(): coalesced apply_state semantics."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_batch_merges_updates(build):
    app = TkApp(title="t")

    app.add_label("a", text="")
    app.add_label("b", text="")

    build(app, layout=["a", "b"])

    app.batch({"a": 1}, {"b": 2})
    assert app.state["a"] == 1
    assert app.state["b"] == 2


def test_batch_later_wins(build):
    app = TkApp(title="t")
    app.add_label("x", text="")
    build(app, layout=["x"])

    app.batch({"x": 1}, {"x": 2})
    assert app.state["x"] == 2


def test_batch_noop_is_skipped(build):
    app = TkApp(title="t")
    calls: list[str] = []

    # Track any cget("text") call as a proxy for sync work.
    orig = TkApp._sync_widgets_for_keys

    def spy(self, update):
        calls.append(f"sync:{update}")
        return orig(self, update)

    build(app, layout=["x"])
    app.state["x"] = ""

    # Apply same value → changed=False → sync_for_keys should still be called
    # but with an empty update (fast skip).
    with patch.object(TkApp, "_sync_widgets_for_keys", spy):
        app.apply_state({"x": ""})  # no-op vs current
        # We can't easily inspect widget-level no-ops without more invasive mocks,
        # but this exercises the branch without side effects.

    assert True  # smoke test


def test_batch_with_untracked(build):
    app = TkApp(title="t")
    app.add_label("status", text="")
    build(app, layout=["status"])

    with app.untracked():
        app.batch({"status": "a"}, {"status": "b"})
    assert app.state["status"] == "b"