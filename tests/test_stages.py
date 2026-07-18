"""stages: regression tests for state-driven stage switching."""

from __future__ import annotations

from nextpytk import TkApp, Layout

from .conftest import requires_display

pytestmark = requires_display


def test_setup_stages_builds_without_mainloop():
    app = TkApp(title="t")

    @app.label("title", role="heading")
    def title():
        return "Title"

    with app.view("home") as v:
        @v.label("home_body")
        def home_body():
            return "home"

    with app.view("settings") as v:
        @v.label("settings_body")
        def settings_body():
            return "settings"

    root = app._setup_stages(
        name="order",
        stages=["home", "settings"],
        key="screen",
        toplevel_widgets=("title",),
        initial_state={"screen": "home"},
        view_layouts={
            "home": Layout().section("home_body"),
            "settings": Layout().section("settings_body"),
        },
        on_ready=lambda a: a.root.withdraw() if a.root is not None else None,
    )
    assert root is not None
    try:
        assert app.widget("title") is not None
        assert app.widget("home_body") is not None
        assert app.widget("settings_body") is not None
        assert app.view_widget_names("home") == ["home_body"]
        assert app.view_widget_names("settings") == ["settings_body"]
        assert app._current_stage == "home"
    finally:
        root.destroy()


def test_apply_state_changes_stage():
    app = TkApp(title="t")

    with app.view("home") as v:
        @v.label("home_body")
        def home_body():
            return "home"

    with app.view("settings") as v:
        @v.label("settings_body")
        def settings_body():
            return "settings"

    root = app._setup_stages(
        name="order",
        stages=["home", "settings"],
        key="screen",
        initial_state={"screen": "home"},
        view_layouts={
            "home": Layout().section("home_body"),
            "settings": Layout().section("settings_body"),
        },
        on_ready=lambda a: a.root.withdraw() if a.root is not None else None,
    )
    assert root is not None
    try:
        assert app._current_stage == "home"
        home_frame = app._stage_frames["home"]
        settings_frame = app._stage_frames["settings"]
        assert home_frame.winfo_manager() == "pack"
        assert settings_frame.winfo_manager() == ""

        app.apply_state({"screen": "settings"})
        assert app._current_stage == "settings"
        assert home_frame.winfo_manager() == ""
        assert settings_frame.winfo_manager() == "pack"

        app.apply_state({"screen": "home"})
        assert app._current_stage == "home"
    finally:
        root.destroy()


def test_invalid_stage_key_is_ignored():
    app = TkApp(title="t")

    with app.view("home") as v:
        @v.label("home_body")
        def home_body():
            return "home"

    root = app._setup_stages(
        name="order",
        stages=["home"],
        key="screen",
        initial_state={"screen": "home"},
        view_layouts={"home": Layout().section("home_body")},
        on_ready=lambda a: a.root.withdraw() if a.root is not None else None,
    )
    assert root is not None
    try:
        app.apply_state({"screen": "missing"})
        # Rejected invalid stage; state/key rolled back to current stage.
        assert app._current_stage == "home"
        assert app.state.get("screen") == "home"
    finally:
        root.destroy()


def test_stages_run_entry_rejects_missing_declaration():
    app = TkApp(title="t")
    try:
        app.run(stages="missing")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "Stages 'missing' is not declared" in str(e)


def test_stages_run_entry_rejects_combined_layout():
    app = TkApp(title="t")
    from nextpytk import Layout
    try:
        app.run(layout=Layout().section("x"), stages="x")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "Only one of layout, multiview, or stages" in str(e)
