"""nextpytk grid layout sample: temperature converter.

Demonstrates fluent grid builder with widget/next_row/col_weight/end_grid.
"""

from nextpytk import TkApp, Layout
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
    .col_weights(0, 1)
    .col_minsizes(140, 120)
    .row_weights(1, 1, 1)
    .span(2).widget("note", sticky=Sticky.NSEW)
    .next_row()
    .widget("celsius_lbl").widget("celsius", sticky=Sticky.EW, padx=4)
    .next_row()
    .widget("fahrenheit_lbl").widget("fahrenheit", sticky=Sticky.EW, padx=4)
    .end_grid()
)

if __name__ == "__main__":
    app.run(layout=layout)
