"""Layout.wrap demo — Flutter-style wrapping and flex.

Three blocks demonstrate the Flutter-derived layout vocabulary added in 0.5:

1. ``wrap`` — a wrapping flow (Flutter ``Wrap`` analog). Widgets fill a row
   left-to-right and wrap onto the next row when they no longer fit. Width is
   content-driven; ``gapx``/``gapy`` (SPACE tokens) control in-row and
   row-to-row spacing. This is the successor to the pre-0.5 ``cluster``.

2. ``wrap`` + ``Flex`` — a wrap child that absorbs leftover horizontal space in
   its row (Flutter ``Expanded`` analog). Here the ``search`` entry grows to
   fill the gap between the two buttons while the buttons keep their natural
   width.

3. ``wrap`` — checkboxes reflow independently.

Resize the window to watch wrap reflow.
"""

from nextpytk import TkApp, Layout, Flex
from nextpytk.types import Fill

app = TkApp(title="Wrap / Flex Demo")


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


@app.entry("search", placeholder="Search terms", width=30)
def on_search(value):
    return {}


@app.button("filter", label="Filter")
def on_filter(values):
    return {"msg": "Filtered"}


@app.checkbutton("active", text="Active")
def on_active(value):
    return {"msg": f"active={value}"}


@app.checkbutton("verbose", text="Verbose")
def on_verbose(value):
    return {"msg": f"verbose={value}"}


@app.checkbutton("confirm", text="Confirm")
def on_confirm(value):
    return {"msg": f"confirm={value}"}


# Shared vertical rhythm across the blocks.
_GAPY = 2  # SPACE[2] = 8px
_PADY = 12

app.run(
    geometry="720x480",
    layout=Layout(spacing=2)
    .section("msg")
    # 1. wrap: buttons + entry reflow onto new rows as the window narrows.
    .wrap(
        "greet", "name", "upper", "clear",
        fill=Fill.X,
        gapx=2,   # SPACE[2] = 8px horizontal gap
        gapy=_GAPY,
        pady=_PADY,
    )
    # 2. wrap + Flex: the search entry absorbs leftover width in its row.
    .wrap(
        "filter",
        Flex("search", flex=2),
        "ok",
        fill=Fill.X,
        gapx=2,
        gapy=_GAPY,
        pady=_PADY,
    )
    # 3. wrap: checkboxes reflow independently.
    .wrap(
        "active", "verbose", "confirm",
        fill=Fill.X,
        gapx=1,
        gapy=_GAPY,
        pady=_PADY,
    )
)
