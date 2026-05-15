"""Flask-style decorator sample: Flask-inspired decorator API with DI layout.

Usage::

    uv run python examples/tkouter_sample.py
"""

from tkouter import TkApp, Layout

app = TkApp(title="Flask-style decorator サンプル")


@app.status("status", description="現在の状態を表示")
def status():
    return "待機中"


@app.button("submit", label="送信", enabled_if=lambda v: bool((v.get("input") or "").strip()))
def on_submit(values):
    return {"status": f"送信しました: {values.get('input', '')}"}


@app.button("clear", label="クリア")
def on_clear(values):
    return {"status": "待機中", "input": ""}


@app.entry("input", placeholder="入力してください")
def on_change(value):
    if not value:
        return {"status": "待機中"}
    return {"status": f"入力中: {value}"}


layout = (
    Layout()
    .section("status")
    .section("input")
    .section("submit", "clear")
)

if __name__ == "__main__":
    app.run(layout=layout)
