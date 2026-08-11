"""Nested frame demo — group widgets with independent inner layouts."""

from nextpytk import TkApp, Layout
from nextpytk.types import Fill, Sticky

app = TkApp(title="Nested Frame Demo")


@app.status("msg")
def msg():
    return "Ready"


@app.button("ok")
def on_ok(values):
    return {"msg": "OK clicked"}


@app.button("cancel")
def on_cancel(values):
    return {"msg": "Cancel clicked"}


@app.entry("name")
def name():
    return ""


@app.entry("email")
def email():
    return ""


# Two independent form groups, each with its own pack-based layout.
name_group = Layout().section("name")
email_group = Layout().section("email")

# Main layout: a grid with the two groups side-by-side, plus a bottom row of
# buttons. The groups use pack internally while the outer shell uses grid,
# avoiding the "cannot mix pack and grid in the same parent" Tk rule.
main = (
    Layout()
    .grid(fill=Fill.BOTH, expand=True)
    .cell("name_group", "email_group", sticky=Sticky.NSEW)
    .end_grid()
    .section("ok", "cancel")
    .frame("name_group", name_group)
    .frame("email_group", email_group)
)

app.run(layout=main)
