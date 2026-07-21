"""Entry widget-level event bindings (events= option)."""

from __future__ import annotations

from typing import Any

from nextpytk import TkApp
from nextpytk.types import EventSeq

from tests.conftest import requires_display

pytestmark = requires_display


def test_entry_event_receives_live_entry_values(build):
    """events= handler receives a dict with the current effective entry values."""
    app = TkApp(title="t")
    seen: dict[str, Any] = {}

    @app.entry(
        "query",
        placeholder="search",
        events={
            EventSeq.RETURN: lambda values: seen.update(values) or {},
        },
    )
    def on_query(value: str) -> dict[str, Any]:
        return {}

    build(app, layout=["query"], initial_state={"query": "hello"})
    spec = app._spec("query")
    assert spec is not None
    handler = spec.extras["events"][EventSeq.RETURN]
    app._on_entry_event(handler)
    assert seen.get("query") == "hello"


def test_entry_event_applies_state_update(build):
    """events= handler can return a state update dict that reaches app.state."""
    app = TkApp(title="t")

    @app.status("msg")
    def msg() -> str:
        return "idle"

    @app.entry(
        "query",
        events={
            EventSeq.RETURN: lambda values: {
                "msg": f"search:{(values.get('query') or '').strip()}"
            },
        },
    )
    def on_query(value: str) -> dict[str, Any]:
        return {}

    build(app, layout=["query", "msg"], initial_state={"query": "test-value"})
    spec = app._spec("query")
    assert spec is not None
    handler = spec.extras["events"][EventSeq.RETURN]
    app._on_entry_event(handler)
    assert app.state["msg"] == "search:test-value"
    msg_widget = app.widget("msg")
    assert msg_widget is not None
    assert msg_widget.cget("text") == "search:test-value"


def test_entry_event_ignores_none_return(build):
    """Returning None must not raise or alter state."""
    app = TkApp(title="t")

    @app.entry(
        "query",
        events={
            EventSeq.RETURN: lambda values: None,
        },
    )
    def on_query(value: str) -> dict[str, Any]:
        return {}

    build(app, layout=["query"])
    spec = app._spec("query")
    assert spec is not None
    handler = spec.extras["events"][EventSeq.RETURN]
    app._on_entry_event(handler)  # should not raise


def test_entry_event_tk_binding_registered(build):
    """The specified event sequence is actually bound to the entry widget."""
    app = TkApp(title="t")

    @app.entry(
        "query",
        events={
            EventSeq.RETURN: lambda values: {"status": "submitted"},
        },
    )
    def on_query(value: str) -> dict[str, Any]:
        return {}

    build(app, layout=["query"])
    w = app.widget("query")
    assert w is not None
    script = w.bind(EventSeq.RETURN)
    assert script, "entry widget must have <Return> binding"


def test_entry_multiple_events_supported(build):
    """events= can carry several handlers for different sequences."""
    app = TkApp(title="t")
    log: list[str] = []

    @app.entry(
        "query",
        events={
            EventSeq.RETURN: lambda values: log.append("return") or {},
            EventSeq.ESCAPE: lambda values: log.append("escape") or {},
        },
    )
    def on_query(value: str) -> dict[str, Any]:
        return {}

    build(app, layout=["query"])
    spec = app._spec("query")
    assert spec is not None
    handlers = spec.extras["events"]
    app._on_entry_event(handlers[EventSeq.RETURN])
    app._on_entry_event(handlers[EventSeq.ESCAPE])
    assert log == ["return", "escape"]
