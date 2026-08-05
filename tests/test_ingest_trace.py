"""Tcl-var trace ingest (v0.4.8): user edits flow back into ``state`` in a batched pass.

With ``ingest_trace=True``, writing to a Tcl variable (typing into an entry,
toggling a checkbutton, dragging a scale) updates ``state[key]`` via a
``trace_add("write")`` and a single ``after_idle`` flush. Without the flag
(the default), behavior is unchanged: state is only updated by ``apply_state``.
"""

from __future__ import annotations

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def _flush_idle(app) -> None:
    """Run pending idle callbacks so the batched ingest flush fires."""
    if app._root is not None:
        app._root.update_idletasks()


def test_typing_into_entry_updates_state(build):
    app = TkApp(title="t", ingest_trace=True)

    @app.entry("query")
    def on_query():
        return {}

    build(app, layout=["query"])
    assert app.state.get("query") in (None, "")

    app._tk_vars["query"].set("py")
    _flush_idle(app)
    assert app.state.get("query") == "py"


def test_batched_flush_coalesces_multiple_edits(build):
    """Multiple edits before idle collapse into a single sync pass."""
    app = TkApp(title="t", ingest_trace=True)
    sync_calls: list[int] = []

    @app.entry("query")
    def on_query():
        return {}

    original = app._apply_state_dict

    def counting(*args, **kwargs):
        sync_calls.append(len(kwargs.get("update") or args[0] or {}))
        return original(*args, **kwargs)

    app._apply_state_dict = counting  # type: ignore[method-assign]
    build(app, layout=["query"])

    var = app._tk_vars["query"]
    var.set("a")
    var.set("ab")
    var.set("abc")
    _flush_idle(app)

    # All three edits coalesce into one flushed update.
    assert sync_calls == [1]
    assert app.state.get("query") == "abc"


def test_framework_writes_do_not_loop_back(build):
    """apply_state-originated var.set must not re-ingest into state."""
    app = TkApp(title="t", ingest_trace=True)

    @app.entry("query")
    def on_query():
        return {}

    build(app, layout=["query"])
    # Set through apply_state (the framework path).
    app.apply_state({"query": "from-framework"})
    _flush_idle(app)
    # State stays the framework value; no trace loop flips it back.
    assert app.state.get("query") == "from-framework"


def test_ingest_disabled_by_default_preserves_lazy_read(build):
    """Without ingest_trace, typing does not touch state until read via values."""
    app = TkApp(title="t")

    @app.entry("query")
    def on_query():
        return {}

    build(app, layout=["query"])
    app._tk_vars["query"].set("typed")
    _flush_idle(app)
    # Default behavior: state is not updated by the var write.
    assert app.state.get("query") not in ("typed",)


def test_scale_keeps_python_int_value(build):
    """Non-string vars (scale) keep their Python-typed value in state."""
    app = TkApp(title="t", ingest_trace=True)

    @app.scale("level", from_=0, to=10)
    def on_scale(value):
        return {}

    build(app, layout=["level"])
    var = app._tk_vars["level"]
    var.set("7")
    _flush_idle(app)
    # The scale's state key is typed as int by the framework; the ingest
    # feeds the Tcl string through the same per-widget key semantics.
    assert app.state.get("level") == 7
