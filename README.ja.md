# README.md: tkouter — Flask-style Decorator API for Tkinter

tkouter は、Tkinter を Flask のデコレータ記法でラップする GUI フレームワーク。
「人間にとってアクセシブルなものは、AI にとってもアクセシブルである」という信念のもと、
A11y 属性（role / description）を WidgetSpec に組み込み、`schema()` で JSON エクスポート可能。

---

## 1. コンセプト

### 1.1 Decorator API（Flask ライク）

最小限の例:

```python
from tkouter import TkApp, Layout

app = TkApp(title="Hello")

@app.status("msg")
def msg():
    return "こんにちは"

@app.button("greet", label="あいさつ")
def on_greet(values):
    return {"msg": "ボタンが押されました！"}

layout = Layout().section("msg").section("greet")
app.run(layout=layout)
```

### 1.2 Notebook（マルチタブ）

`@app.notebook` デコレータでマルチビュー（タブ切替）の設定を宣言、
`app.run(notebook="name")` で起動する。

```python
from tkouter import TkApp, Layout

app = TkApp(title="マルチタブアプリ")

# ── 全画面共通ウィジェット ──
@app.status("header")
def header(): return "共通ヘッダー"

# ── 各タブのビュー（layout 付き） ──
with app.view("Tab1", layout=Layout().section("t1_label", "t1_btn")) as v:
    @v.label("t1_label")
    def t1_label(): return "タブ1 の内容"

    @v.button("t1_btn", label="クリック")
    def t1_btn(vals): return {}

with app.view("Tab2", layout=Layout().section("t2_label")) as v:
    @v.label("t2_label")
    def t2_label(): return "タブ2 の内容"

# ── Notebook 宣言 ──
@app.notebook(
    "main",
    views=["Tab1", "Tab2"],
    toplevel_widgets=("header",),
    initial_state={"tab": "Tab1"},
    on_tab_change=lambda tab: {"tab": tab},
)
def main_notebook(): pass

app.run(notebook="main")
```

### 1.3 IoC レイアウト（DI）

- ウィジェットの「登録」と「配置」を分離
- `Layout.section(...)` — pack ベースのセクション
- `Layout.grid()` — fluent grid ビルダー

```python
from tkouter import TkApp, Layout
from tkouter.types import Sticky

layout = (
    Layout()
    .section("title")
    .grid()
    .widget("name_lbl", sticky=Sticky.RIGHT).widget("name", sticky=Sticky.LEFT_RIGHT)
    .next_row()
    .span(2).widget("ok")
    .end_grid()
)
```

### 1.4 型付きオプション（IDE 補完）

`tkouter.types` が Tkinter の文字列定数を Literal 型 + 名前空間クラスで提供。

```python
from tkouter.types import Side, Fill, Sticky

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
# または直接文字列でも OK: side="left", fill="x"
```

### 1.5 A11y First & Agent Ready

```python
@app.status("msg", role="status", description="操作結果")
def msg():
    return "待機中"

# schema() で Agent/LLM 向け JSON を出力
print(app.schema())
# → {"title": "...", "widgets": [{"name": "msg", "kind": "status", "role": "status", ...}]}
```

---


```bash
cd tk-outer
uv sync --python 3.14
```

> 注: 一部の macOS 環境では `uv` の `3.14+freethreaded` で Tk 起動時に `Can't find a usable init.tcl` が発生します。
> 実行時に `PYTHON=...` を切り替えできます（例: `make run PYTHON=3.13` / `make run PYTHON=3.14+freethreaded` / `make run PYTHON=3.15`）。
> `3.14` 実行時に同エラーが出る場合は、uv 管理 Python の Tcl/Tk パスを明示すると回避できます:
>
> ```bash
> UV_PY314="$(ls -d "$HOME"/.local/share/uv/python/cpython-3.14.*-macos-aarch64-none | head -n 1)"
> TCL_LIBRARY="$UV_PY314/lib/tcl8.6" \
> TK_LIBRARY="$UV_PY314/lib/tk8.6" \
> uv run --python 3.14 python examples/tkouter_grid_temp.py
> ```

---

## 2. クイックスタート

### 3.1 温度変換（grid レイアウト）

```python
from tkouter import TkApp, Layout
from tkouter.types import Sticky

app = TkApp(title="温度変換")

@app.label("title", role="heading")
def title():
    return "摂氏 ↔ 華氏 変換"

@app.entry("celsius", placeholder="0", placeholder_as_hint=False)
def on_celsius(value):
    try:
        return {"fahrenheit": f"{float(value) * 9/5 + 32:.1f}"}
    except ValueError:
        return {"fahrenheit": "---"}

@app.entry("fahrenheit", placeholder="32", placeholder_as_hint=False)
def on_fahrenheit(value):
    try:
        return {"celsius": f"{(float(value) - 32) * 5/9:.1f}"}
    except ValueError:
        return {"celsius": "---"}

@app.status("note")
def note():
    return "どちらかの値を入力すると自動変換されます"

layout = (
    Layout()
    .section("title")
    .grid()
    .col_weights(0, 1)
    .span(2).widget("note", sticky=Sticky.LEFT)
    .next_row()
    .widget("celsius", sticky=Sticky.LEFT_RIGHT, padx=4).widget("fahrenheit", sticky=Sticky.LEFT_RIGHT, padx=4)
    .end_grid()
)

app.run(layout=layout)
```

### 3.2 マルチスクリーン注文アプリ

画面遷移・状態管理の実例は `examples/tkouter_multiscreen.py` を参照。

---

## 非同期 Native（asyncio + Tkinter）

`app.run_async()` は asyncio イベントループ上でアプリを実行し、
`root.tk.dooneevent(0)` を使って Tk メインループと協調動作する。
`app.spawn(coro)` で GUI 実行中に非同期タスクをスケジュールできる。
`@app.job(name)` デコレータで非同期コールバックを登録する。

```python
@app.job("scan")
async def scan(vals):
    result = await asyncio.to_thread(some_blocking_call)
    return {"status": "done"}

app.run_async(layout=Layout().section("status"))
```

## 3. サンプル一覧

| ファイル | 内容 |
|----------|------|
| `examples/tkouter_grid_temp.py` | grid レイアウト・温度変換 |
| `examples/tkouter_task_panel.py` | 複数ラベル＋エントリ＋ボタンの状態管理 |
| `examples/tkouter_multiscreen.py` | 画面遷移・注文アプリ |
| `examples/tkouter_widget_gallery.py` | 全ウィジェット種別＋ttk.Notebook によるタブ切替 |
| `examples/disk_usage_flat_viewer.py` | ディスク使用量フラットビューア（同期版、ncdu風） |
| `examples/disk_usage_flat_async.py` | ディスク使用量フラットビューア（非同期版、ncdu風） |

```bash
uv run python examples/tkouter_grid_temp.py
uv run python examples/tkouter_task_panel.py
uv run python examples/tkouter_multiscreen.py
uv run python examples/tkouter_widget_gallery.py
uv run python examples/disk_usage_flat_viewer.py
uv run python examples/disk_usage_flat_async.py
```

---

## 4. ウィジェット一覧

| デコレータ | ウィジェット種別 | コールバック引数 | 返り値 |
|------------|------------------|------------------|--------|
| `@app.label(name, font=..., anchor=..., justify=..., padding=...)` | tk.Label | なし | `str` または `dict` |
| `@app.status(name)` | tk.Label (role=status) | なし | `str` または `dict` |
| `@app.message(name, width=..., auto_width=...)` | tk.Label (wrap) | なし | `str` または `dict` |
| `@app.button(name, label=..., state=..., enabled_if=...)` | ttk.Button | `dict` (entry values) | `dict` (state update) |
| `@app.job(name)` | async callable | `dict` (entry values) | `dict` (state update) |
| `@app.entry(name, placeholder=..., show=..., width=...)` | ttk.Entry | `str` (値) | `dict` (state update) |
| `@app.checkbutton(name, text=...)` | ttk.Checkbutton | `bool` | `dict` |
| `@app.radiobutton(name, text=..., value=..., group=...)` | ttk.Radiobutton | `str` (値) | `dict` |
| `@app.text(name, width=..., height=...)` | tk.Text | `str` (全内容) | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | `str` (値) | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=...)` | ttk.Spinbox | `str` (値) | `dict` |
| `@app.listbox(name, items=..., selectmode=...)` | tk.Listbox | `str` (選択項目) | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | なし | — |

### label の拡張オプション

- `font`: フォント指定。例: `font=("TkDefaultFont", 18, "bold")`
- `anchor`: テキストの配置位置。例: `anchor="e"`（右寄せ）
- `justify`: 複数行テキストの行揃え。例: `justify="right"`
- `padding`: 内側の余白。例: `padding=4` または `padding=(4, 2)`

### message ウィジェット

`@app.message(name)` は自動折り返しのラベル。
`width` で初期幅（px）を指定、`auto_width=True`（デフォルト）で親コンテナの幅に追従する。

---

## 5. Grid Builder API リファレンス

`Layout.grid()` は `_GridBuilder` を返す。チェーンしてウィジェットを配置する。

### 配置

| メソッド | 説明 |
|----------|------|
| `widget(name, *, sticky, padx, pady, colspan, rowspan)` | 現在位置にウィジェットを配置、列を進める。`rowspan` で複数行にまたがるウィジェットを指定 |
| `span(cols)` | 次の `widget()` の列スパンを設定（1回限り） |
| `next_row()` | 次の行の先頭列へ移動 |
| `next_col(n=1)` | n 列スキップ |
| `at(row, col)` | 絶対位置へジャンプ |

### 列・行設定

| メソッド | 説明 |
|----------|------|
| `col_weights(*weights)` | 列の重みを位置順に一括設定。例: `col_weights(0, 1, 1)` |
| `row_weights(*weights)` | 行の重みを位置順に一括設定。例: `row_weights(0, 1)` |
| `col_weight(col, weight=1)` | 1列だけ重みを設定（個別上書き用） |
| `row_weight(row, weight=1)` | 1行だけ重みを設定 |
| `col_minsize(col, minsize)` | 列の最小幅 |
| `row_minsize(row, minsize)` | 行の最小高さ |

### grid() のオプション

| オプション | 説明 |
|------------|------|
| `uniform` | 同じ名前の列同士を同じ幅に揃える。`columnconfigure(col, uniform=...)` に展開 |
| `padx`, `pady` | フレーム全体のパディング |
| `fill` | フレームの pack fill |
| `expand` | フレームの pack expand |

### 終了

| メソッド | 説明 |
|----------|------|
| `end_grid()` | grid ブロックを終了し、`Layout` チェーンに戻る |

---

## 6. 設計思想

### Web の三層構造との対応

| Web | tkouter |
|-----|---------|
| HTML（マークアップ） | `@app.label(...)` / `@app.button(...)` によるウィジェット登録 |
| CSS（スタイル） | 将来: Tk option / ttk.Style を `Layout` 経由で注入 |
| JavaScript（インタラクション） | デコレータ付きコールバック関数 + `_apply_state` → `_sync_widgets` |

### 既存ライブラリとの関係

- **`tkinter`（標準）**: ベースとして尊重。tkouter はその上に Decorator / Schema / A11y 層を載せる
- **`ttk`**: OS ネイティブな見た目と A11y を継承。将来 ttk widget 対応予定
- **`CustomTkinter`**: モダン L&F の先行事例。Canvas 描画が A11y 的に空白になる課題に対し、tkouter は A11y を最初から組み込む

---

## 7. ライセンス

MIT License

## 8. 著者

西本卓也 (Takuya Nishimoto) — 株式会社シュアルタ
