"""tkouter demo: labels, entries, buttons updating a **shared state dict**.

Shows the decorator API + section-based layout.
"""

from tkouter import TkApp, Layout

app = TkApp(title="tkouter task panel")


# --- Status row ---

@app.status("msg", description="操作結果のフィードバック")
def msg():
    return "準備完了"


@app.status("phase", description="現在のフェーズ")
def phase():
    return "待機中"


@app.status("count", description="処理件数")
def count():
    return "0 件"


# --- Inputs ---

@app.entry("name", placeholder="タスク名（必須）")
def on_name_change(value):
    return {"msg": f"タスク名: {value}"}


@app.entry("max_sec", placeholder="最大秒数（例: 5）")
def on_sec_change(value):
    return {"msg": f"タイムアウト: {value}秒"}


# --- Actions ---

PHASE = {"idle": "待機中", "running": "実行中", "done": "完了", "paused": "一時停止"}


@app.button("start", label="▶ 開始")
def on_start(values):
    name = values.get("name", "").strip()
    if not name:
        return {"msg": "タスク名を入力してください"}
    return {"msg": f"「{name}」を開始", "phase": PHASE["running"]}


@app.button("pause", label="⏸ 一時停止")
def on_pause(values):
    return {"msg": "一時停止", "phase": PHASE["paused"]}


@app.button("reset", label="⏹ リセット")
def on_reset(values):
    return {"msg": "リセットしました", "phase": PHASE["idle"], "count": "0 件"}


@app.button("countup", label="+1")
def on_countup(values):
    c = app.state.get("count", "0 件")
    n = 1
    if c.endswith(" 件"):
        try:
            n = int(c.split()[0]) + 1
        except ValueError:
            pass
    return {"count": f"{n} 件", "msg": f"カウント: {n}"}


# --- Layout ---

layout = (
    Layout()
    .section("msg")
    .section("phase", "count")
    .section("name", fill="x")
    .section("max_sec", fill="x")
    .section("start", "pause")
    .section("reset", "countup")
)

if __name__ == "__main__":
    app.run(layout=layout)
