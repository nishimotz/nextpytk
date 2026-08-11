"""nextpytk grid layout sample: temperature converter.

Demonstrates fluent grid builder with cell/next_row/col_weight/end_grid.
"""

from nextpytk import TkApp, Layout
from nextpytk.tokens import SPACE
from nextpytk.types import Anchor, Fill, Sticky

app = TkApp(title="Temperature conversion")


@app.label("title", role="heading", description="Title")
def title():
    return "Celsius ↔ Fahrenheit conversion"


@app.label("celsius_lbl", width=17, anchor=Anchor.E)
def celsius_lbl():
    return "Celsius (°C):"


@app.entry("celsius", placeholder="0", placeholder_as_hint=False)
def on_celsius(value):
    try:
        c = float(value)
        result = {"fahrenheit": f"{c * 9/5 + 32:.1f}"}
    except ValueError:
        result = {"fahrenheit": "---"}
    return result


@app.label("fahrenheit_lbl", width=17, anchor=Anchor.E)
def fahrenheit_lbl():
    return "Fahrenheit (°F):"


@app.entry("fahrenheit", placeholder="32", placeholder_as_hint=False)
def on_fahrenheit(value):
    try:
        f = float(value)
        result = {"celsius": f"{(f - 32) * 5/9:.1f}"}
    except ValueError:
        result = {"celsius": "---"}
    return result


@app.status("note", description="Help")
def note():
    return "Enter a value in either field to convert automatically"


layout = (
    Layout()
    .section("title")
    .grid(fill=Fill.BOTH, expand=True)
    .col_weight(0, 0)
    .col_weight(1, 1)
    .col_minsize(0, 140)
    .col_minsize(1, 120)
    .row_weight(0, 1)
    .row_weight(1, 1)
    .row_weight(2, 1)
    .span(2).cell("note", sticky=Sticky.NSEW)
    .next_row()
    .cell("celsius_lbl", "celsius", sticky=Sticky.EW, padx=SPACE[1])
    .next_row()
    .cell("fahrenheit_lbl", "fahrenheit", sticky=Sticky.EW, padx=SPACE[1])
    .end_grid()
)

if __name__ == "__main__":
    app.run(layout=layout)
