"""Tab focus demo — ``takefocus`` on nextpytk widgets.

Tab through the form: name → email → agree → submit.
The hint label and status line are skipped (``takefocus=0``).

フォーカス枠 — Tcl/Tk の整理
-----------------------------

* **クラシック tk**（``tk.Entry`` 等）: ``-highlightthickness`` /
  ``-highlightcolor`` が traversal highlight（options マニュアル）。
* **ttk**: ``-highlightthickness`` 非対応。各 OS の Aqua / Windows / GTK
  テーマがキーボードフォーカス時の枠を描く（例: macOS 8.6.14 ライトモードは
  ``kThemeAdornmentFocus``、Entry は青〜水色の枠）。
* **macOS ダークモード**: Button / Checkbutton はフォーカス枠が弱い／無い
  ことがある（``DrawDarkButton`` 経路）。必要ならアプリ側で別途対応。
* **takefocus**: Tab 巡回の可否は ``TakeFocus`` / ``takefocus=`` で制御。
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import TakeFocus

app = TkApp(title="Tab focus — takefocus demo")

layout = (
    Layout()
    .section("hint")
    .section("name", "email")
    .section("agree")
    .section("submit")
    .section("status")
)


@app.label("hint", takefocus=TakeFocus.NO)
def hint():
    return "Tab で name → email → 同意 → 送信 の順に移動します"


@app.entry("name", placeholder="名前", takefocus=TakeFocus.YES)
def name(value: str):
    return {"status": f"name: {value!r}"}


@app.entry("email", placeholder="メール", takefocus=TakeFocus.YES)
def email(value: str):
    return {"status": f"email: {value!r}"}


@app.checkbutton("agree", text="同意する", takefocus=TakeFocus.YES)
def agree(checked: bool):
    return {"status": f"agree: {checked}"}


@app.button("submit", label="送信", takefocus=TakeFocus.YES)
def submit(_vals):
    return {"status": "submitted"}


@app.status("status", takefocus=TakeFocus.NO)
def status():
    return str(app.state.get("status", "—"))


if __name__ == "__main__":
    app.run(layout=layout)
