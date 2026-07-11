"""@app.bind: global key bindings — sequence registration, state dispatch, button annotation."""

from __future__ import annotations

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def _bind_spec(app: TkApp, name: str):
    for spec in app.widget_specs(kind="bind"):
        if spec.name == name:
            return spec
    raise AssertionError(f"bind spec {name!r} not found")


def test_bind_registers_sequence(build, harness):
    app = TkApp(title="t")

    @app.bind("save", sequence="<Control-s>", label="Ctrl+S")
    def save(state):
        return {}

    build(app)
    script = harness.root.bind_all("<Control-s>")
    assert script, "bind_all sequence must be registered"


def test_bind_trigger_applies_state_and_refreshes_label(build):
    """Dict returned from a bind handler must reach both state and widgets."""
    app = TkApp(title="t")

    @app.label("status_bar")
    def status_bar():
        return "idle"

    @app.bind("save", sequence="<Control-s>", label="Ctrl+S")
    def save(state):
        return {"status_bar": "saved"}

    build(app, layout=["status_bar"])
    spec = _bind_spec(app, "save")
    app._on_bind_trigger(spec, spec.on_click)

    assert app.state["status_bar"] == "saved"
    assert app.widget("status_bar").cget("text") == "saved"


def test_bind_handler_receives_current_state(build):
    app = TkApp(title="t")
    seen: dict = {}

    @app.label("msg")
    def msg():
        return ""

    @app.bind("probe", sequence="<Control-p>")
    def probe(state):
        seen.update(state)
        return {}

    build(app, layout=["msg"], initial_state={"msg": "hello"})
    spec = _bind_spec(app, "probe")
    app._on_bind_trigger(spec, spec.on_click)
    assert seen.get("msg") == "hello"


def test_bind_annotates_matching_button(build):
    app = TkApp(title="t")

    @app.button("save", label="Save")
    def save_btn(values):
        return {}

    @app.bind("save", sequence="<Control-s>", label="Ctrl+S")
    def save_key(state):
        return {}

    build(app, layout=["save"])
    assert "Ctrl+S" in str(app.widget("save").cget("text"))
