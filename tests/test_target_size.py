"""Interactive target size (WCAG 2.5.5 Target Size: 44px square).

Buttons and nav-style controls should request at least MIN_TARGET height.
Tk widgets get there via theme padding; these tests pin the real size.
"""

from __future__ import annotations

import pytest

from nextpytk import TkApp
from nextpytk import tokens as t

from .conftest import requires_display

pytestmark = requires_display


@pytest.fixture
def sized(build):
    app = TkApp(title="t")

    @app.button("go", label="Run")
    def go(vals):
        return {}

    @app.checkbutton("agree", text="Agree")
    def agree(v):
        return {}

    @app.radiobutton("opt", text="Option", value="a")
    def opt(v):
        return {}

    # NOTE: no update_idletasks() here — on the bundled Tk 9.0.3 (macOS,
    # uv 3.14t) servicing idle events on a withdrawn root segfaults in
    # showRootWindow. winfo_reqheight is computed synchronously anyway.
    build(app, layout=["go", "agree", "opt"])
    return app


@pytest.mark.parametrize("name", ["go", "agree", "opt"])
def test_interactive_widget_meets_min_target_height(sized, name):
    h = sized.widget(name).winfo_reqheight()
    assert h >= t.MIN_TARGET, f"{name}: {h}px < {t.MIN_TARGET}px (WCAG 2.5.5)"
