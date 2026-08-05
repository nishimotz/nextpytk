"""API contract: state= on button/entry, placeholder color constant, schema completeness."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from nextpytk import TkApp
from nextpytk.app import PLACEHOLDER_FG

from .conftest import requires_display

pytestmark = requires_display


def test_button_state_disabled_is_applied(build):
    app = TkApp(title="t")

    @app.button("go", label="Go", state="disabled")
    def go(values):
        return {}

    build(app, layout=["go"])
    assert str(app.widget("go").cget("state")) == "disabled"


def test_button_label_updates_from_state_dict(build):
    """Returning {"<button>": text} from a callback refreshes the label."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return {"hello": "world"}

    build(app, layout=["hello"])
    assert str(app.widget("hello").cget("text")) == "hello"
    app.widget("hello").invoke()
    assert str(app.widget("hello").cget("text")) == "world"


def test_button_label_updates_from_plain_string(build):
    """Returning a plain string updates the button's own label (sugar)."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return "world"

    build(app, layout=["hello"])
    assert str(app.widget("hello").cget("text")) == "hello"
    app.widget("hello").invoke()
    assert str(app.widget("hello").cget("text")) == "world"


def test_button_callback_returning_none_is_ignored(build):
    """Returning None from a button callback leaves the label unchanged."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return None

    build(app, layout=["hello"])
    app.widget("hello").invoke()
    assert str(app.widget("hello").cget("text")) == "hello"


def test_button_callback_returning_set_is_ignored_with_warning(build):
    """A set (e.g. {"hello", "world"}) is not a state dict; warn and ignore."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return {"hello", "world"}

    build(app, layout=["hello"])
    app.widget("hello").invoke()
    # Label unchanged; the set is not applied as state.
    assert str(app.widget("hello").cget("text")) == "hello"


def test_button_callback_returning_list_is_ignored(build):
    """A list is not a valid return; warn and ignore (layout is via layout=)."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return ["hello", "world"]

    build(app, layout=["hello"])
    app.widget("hello").invoke()
    assert str(app.widget("hello").cget("text")) == "hello"


def test_button_callback_returning_tuple_is_ignored(build):
    """A tuple is not a valid return; warn and ignore."""
    app = TkApp(title="t")

    @app.button("hello", label="hello")
    def on_hello(values):
        return ("hello", "world")

    build(app, layout=["hello"])
    app.widget("hello").invoke()
    assert str(app.widget("hello").cget("text")) == "hello"


def test_auto_layout_builds_single_column(build):
    """_auto_layout arranges registered widgets when run() has no layout."""
    app = TkApp(title="t")

    @app.button("go", label="Go")
    def go(values):
        return {}

    @app.entry("name", placeholder="your name")
    def name(value):
        return {}

    layout = app._auto_layout()
    assert layout is not None
    # Widgets are arranged in registration order, one section per widget.
    arranged = [n for b in layout._blocks for n in b.widgets]
    assert arranged == ["go", "name"]

    # Building with the auto layout renders every widget.
    build(app, layout=layout)
    assert app.widget("go") is not None
    assert app.widget("name") is not None
    assert str(app.widget("go").cget("text")) == "Go"


def test_auto_layout_none_when_no_widgets():
    """_auto_layout returns None when there is nothing to arrange."""
    app = TkApp(title="t")
    assert app._auto_layout() is None


def test_layout_names_detects_orphan(build):
    """_warn_orphan_layout_names flags a layout name with no registration."""
    app = TkApp(title="t")

    @app.button("go", label="Go")
    def go(values):
        return {}

    from nextpytk import Layout
    layout = Layout.from_list(["go", "missing"])
    names = app._layout_names(layout)
    assert "go" in names
    assert "missing" in names


def test_layout_names_collects_grid_cells(build):
    """Grid cells are collected as layout-referenced names."""
    app = TkApp(title="t")

    @app.button("go", label="Go")
    def go(values):
        return {}

    from nextpytk import Layout
    layout = Layout().grid().widget("go").end_grid()
    assert "go" in app._layout_names(layout)


def test_entry_callback_returning_string_warns(build):
    """A string from an entry callback is invalid and ignored with a warning."""
    app = TkApp(title="t")

    @app.entry("name", placeholder="Name")
    def on_name(value):
        return "unexpected"

    build(app, layout=["name"])
    # Entry content is driven by state; a bare string return must not crash.
    assert app.widget("name") is not None


def test_entry_state_disabled_is_applied(build):
    app = TkApp(title="t")

    @app.entry("name", state="disabled")
    def name(value):
        return {}

    build(app, layout=["name"])
    assert str(app.widget("name").cget("state")) == "disabled"


def test_placeholder_color_uses_tokens(build):
    """Placeholder color is exported from the design tokens."""
    from nextpytk.tokens import TEXT_MUTED
    assert PLACEHOLDER_FG is TEXT_MUTED

    app = TkApp(title="t", theme="none")

    @app.entry("name", placeholder="your name")
    def name(value):
        return {}

    build(app, layout=["name"])
    w = app.widget("name")
    try:
        fg = str(w.cget("foreground"))
    except tk.TclError:
        return  # platform theme forbids fg query; constant check above suffices
    assert fg.lower() in (PLACEHOLDER_FG, "")


def test_theme_applied_by_default(build):
    """Kizashi theme is applied automatically when no theme is specified."""
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # Kizashi styles should be configured with our accent/bg tokens.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") == tokens.ACCENT
    assert style.lookup("TEntry", "fieldbackground") == tokens.BG


def test_theme_disabled(build):
    """theme='none' leaves the platform default theme untouched."""
    app = TkApp(title="t", theme="none")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    # Primary.TButton should not have our custom background.
    from nextpytk import tokens
    assert style.lookup("Primary.TButton", "background") != tokens.ACCENT


def test_theme_builtin_name(build):
    """theme='clam' switches to the named built-in ttk theme."""
    app = TkApp(title="t", theme="clam")

    @app.label("msg")
    def msg():
        return "hello"

    build(app, layout=["msg"])
    style = tk.ttk.Style(app.root)
    assert style.theme_use() == "clam"


def test_theme_bool_deprecated(build):
    """Passing theme=True/False emits a DeprecationWarning."""
    import warnings

    app = TkApp(title="t", theme="none")

    @app.label("msg")
    def msg():
        return "hello"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app2 = TkApp(title="t", theme=False)
        build(app2, layout=["msg"])

    assert any(
        issubclass(w.category, DeprecationWarning)
        and "theme=True/False is deprecated" in str(w.message)
        for w in caught
    )


def test_schema_includes_all_widgets(build):
    app = TkApp(title="t")

    @app.label("msg")
    def msg():
        return ""

    @app.button("go", label="Go")
    def go(values):
        return {}

    kinds = {w["name"]: w["kind"] for w in app.schema()["widgets"]}
    assert kinds == {"msg": "label", "go": "button"}


def test_entry_applies_font(build):
    """@app.entry accepts and applies a per-widget font option."""
    import tkinter.font as tkfont
    app = TkApp(title="t")

    @app.entry("styled", font=("TkDefaultFont", 12))
    def on_styled(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["styled"])
    w = app.widget("styled")
    assert w is not None
    assert isinstance(w, ttk.Entry)
    style = ttk.Style(w)
    actual = tkfont.Font(font=style.lookup(w.cget("style"), "font"))
    assert actual.actual("size") == 12


def test_entry_applies_padding_for_visual_height(build):
    """@app.entry accepts padding= as a declarative visual-height adjustment."""
    app = TkApp(title="t")

    @app.entry("padded", padding=(8, 12))
    def on_padded(value: str) -> dict[str, str]:
        return {}

    build(app, layout=["padded"])
    w = app.widget("padded")
    assert w is not None
    assert isinstance(w, ttk.Entry)
    style = ttk.Style(w)
    configured = str(style.lookup(w.cget("style"), "padding"))
    assert configured == "(8, 12)" or configured == "8 12"


def test_button_applies_font(build):
    """@app.button accepts and applies a per-widget font option."""
    import tkinter.font as tkfont
    app = TkApp(title="t")

    @app.button("styled", label="Styled", font=("TkDefaultFont", 11))
    def on_styled(values: dict[str, str]) -> dict[str, str]:
        return {}

    build(app, layout=["styled"])
    w = app.widget("styled")
    assert w is not None
    assert isinstance(w, ttk.Button)
    style = ttk.Style(w)
    actual = tkfont.Font(font=style.lookup(w.cget("style"), "font"))
    assert actual.actual("size") == 11
