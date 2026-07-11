"""nextpytk paned sample — horizontal split with ``with app.pane(...)``."""

from __future__ import annotations

from nextpytk import Layout, TkApp

app = TkApp(title="Paned split")

app.paned(
    "workspace",
    panes=("left", "right"),
    orient="horizontal",
    weights=(1, 2),
    description="左右分割（サッシュをドラッグしてリサイズ）",
)


@app.status("hint")
def hint() -> str:
    return "中央の境界線をドラッグしてペイン幅を変えてください"


with app.pane("left"):
    @app.label("left_title")
    def left_title() -> str:
        return "左ペイン"

    @app.message("left_body")
    def left_body() -> str:
        return "左側のコンテンツです。\n比較ツールでは Location リストなどを置きます。"


with app.pane("right"):
    @app.label("right_title")
    def right_title() -> str:
        return "右ペイン"

    @app.message("right_body")
    def right_body() -> str:
        return "右側のコンテンツです。\nテキスト比較ペインのプレースホルダーとして使えます。"


layout = (
    Layout()
    .section("hint")
    .paned("workspace", minsizes=(160, 200), weights=(1, 2), fill="both", expand=True)
)

if __name__ == "__main__":
    app.run(layout=layout, geometry="520x320")
