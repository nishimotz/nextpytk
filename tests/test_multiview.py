"""multiview: regression tests for _setup_multiview extraction."""

from __future__ import annotations

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def test_setup_multiview_builds_views_without_mainloop():
    app = TkApp(title="t")

    @app.status("header")
    def header():
        return "common"

    with app.view("Tab1") as v:
        @v.label("t1")
        def t1():
            return "tab1 body"

    with app.view("Tab2") as v:
        @v.label("t2")
        def t2():
            return "tab2 body"

    root = app._setup_multiview(
        views=["Tab1", "Tab2"],
        toplevel_widgets=("header",),
        initial_state={"t1": "hello"},
        on_ready=lambda a: a.root.withdraw(),
    )
    try:
        assert app.widget("header") is not None
        assert app.widget("t1").cget("text") == "hello"
        assert app.widget("t2") is not None
        # view registration must go through the ViewContext proxy
        assert app.view_widget_names("Tab1") == ["t1"]
        assert app.view_widget_names("Tab2") == ["t2"]
    finally:
        root.destroy()


def test_view_context_rejects_unknown_attribute():
    app = TkApp(title="t")
    with app.view("Tab1") as v:
        try:
            v.no_such_widget  # noqa: B018
        except AttributeError:
            pass
        else:
            raise AssertionError("expected AttributeError")
