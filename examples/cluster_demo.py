"""Cluster layout demo — mixed widgets wrapped responsively.

A status, several buttons, a wide entry, and a checkbutton are placed in the
same cluster so the responsive wrapping behavior is easy to see. Resize the
window to watch the number of columns change automatically based on widget
widths.
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Cluster Demo")


@app.status("msg")
def msg():
    return "Type and click around"


@app.button("greet", label="Greet")
def on_greet(values):
    name = values.get("name") or "world"
    return {"msg": f"Hello, {name}!"}


@app.button("clear", label="Clear")
def on_clear(values):
    return {"msg": "Cleared", "name": "", "active": False}


@app.button("upper", label="Upper")
def on_upper(values):
    name = (values.get("name") or "").upper()
    return {"name": name, "msg": f"Now: {name}"}


@app.button("ok", label="OK")
def on_ok(values):
    return {"msg": "OK"}


@app.entry("name", placeholder="Name", width=30)
def on_name(value):
    return {}


@app.checkbutton("active", text="Active")
def on_active(value):
    return {"msg": f"active={value}"}


app.run(
    layout=Layout(spacing=2)
    .section("msg")
    .cluster("greet", "name", "active", "upper", "clear", "ok")
)
