"""nextpytk grid layout sample: temperature converter.

Demonstrates fluent grid builder with widget/next_row/col_weight/end_grid.
"""

from nextpytk import TkApp, Layout
from nextpytk.types import Sticky

app = TkApp(title="温度変換")


@app.label("title", role="heading", description="タイトル")
def title():
    return "摂氏 ↔ 華氏 変換"


@app.label("celsius_lbl")
def celsius_lbl():
    return "摂氏 (°C):"


@app.entry("celsius", placeholder="0", placeholder_as_hint=False)
def on_celsius(value):
    try:
        c = float(value)
        result = {"fahrenheit": f"{c * 9/5 + 32:.1f}"}
    except ValueError:
        result = {"fahrenheit": "---"}
    return result


@app.label("fahrenheit_lbl")
def fahrenheit_lbl():
    return "華氏 (°F):"


@app.entry("fahrenheit", placeholder="32", placeholder_as_hint=False)
def on_fahrenheit(value):
    try:
        f = float(value)
        result = {"celsius": f"{(f - 32) * 5/9:.1f}"}
    except ValueError:
        result = {"celsius": "---"}
    return result


@app.status("note", description="ヘルプ")
def note():
    return "どちらかの値を入力すると自動変換されます"


layout = (
    Layout()
    .section("title")
    .grid()
    .col_weights(0, 1)
    .span(2).widget("note", sticky=Sticky.LEFT)
    .next_row()
    .widget("celsius_lbl", sticky=Sticky.RIGHT).widget("celsius", sticky=Sticky.LEFT_RIGHT, padx=4)
    .next_row()
    .widget("fahrenheit_lbl", sticky=Sticky.RIGHT).widget("fahrenheit", sticky=Sticky.LEFT_RIGHT, padx=4)
    .end_grid()
)

if __name__ == "__main__":
    app.run(layout=layout)
