# README.md: nextpytk — Flask-style Decorator API for Tkinter

nextpytk は、Tkinter を Flask のデコレータ記法でラップする GUI フレームワーク。
「人間にとってアクセシブルなものは、AI にとってもアクセシブルである」という信念のもと、
A11y 属性（role / description）を WidgetSpec に組み込み、`schema()` で JSON エクスポート可能。

---

## 1. コンセプト

### 1.1 Decorator API（Flask ライク）

```python
from nextpytk import TkApp, Layout

app = TkApp(title="Hello")

@app.status("msg")
def msg():
    return "こんにちは"

@app.button("greet", label="あいさつ")
def on_greet(values):
    return {"msg": "ボタンが押されました！"}

app.run(layout=Layout().section("msg").section("greet"))
```

### 1.2 3つのレイアウト方式

目的に合わせて選べる:

```python
# 1) シンプルリスト（一番おすすめ）
app.run(layout=["msg", "greet"])

# 2) Fluent DSL（チェーン）
app.run(layout=Layout().section("msg").section("greet"))

# 3) with-block（コンテキストマネージャ）
with app.layout() as b:
    b.section("msg")
    b.section("greet")
app.run(layout=b.build())
```

### 1.3 Multiview（マルチタブ）

`@app.multiview` デコレータでマルチビュー（タブ切替）の設定を宣言、
`app.run(multiview="name")` で起動する。

```python
from nextpytk import TkApp, Layout

app = TkApp(title="マルチタブアプリ")

@app.status("header")
def header(): return "共通ヘッダー"

with app.view("Tab1", layout=Layout().section("t1_label", "t1_btn")) as v:
    @v.label("t1_label")
    def t1_label(): return "タブ1 の内容"
    @v.button("t1_btn", label="クリック")
    def t1_btn(vals): return {}

with app.view("Tab2", layout=Layout().section("t2_label")) as v:
    @v.label("t2_label")
    def t2_label(): return "タブ2 の内容"

@app.multiview(
    "main",
    views=["Tab1", "Tab2"],
    toplevel_widgets=("header",),
    initial_state={"tab": "Tab1"},
    on_tab_change=lambda tab: {"tab": tab},
)
def main_multiview(): pass

app.run(multiview="main")
```

ビューレイアウトにもリストや with-block を使える:

```python
@app.multiview("main", views=["Home", "Settings"],
    view_layouts={"Home": ["title", "start"], "Settings": ["timer", "status"]})
```

### 1.4 IoC レイアウト（DI）

- ウィジェットの「登録」と「配置」を分離
- `Layout.section(...)` — pack ベースのセクション
- `Layout.grid()` — fluent grid ビルダー
- `LayoutBuilder` — with-block コンテキストマネージャ
- `Layout.from_list(...)` — シンプルリスト

### 1.5 型付きオプション（IDE 補完）

`nextpytk.types` が Tkinter の文字列定数を Literal 型 + 名前空間クラスで提供。

```python
from nextpytk.types import Side, Fill, Sticky

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
# または直接文字列でも OK: side="left", fill="x"
```

### 1.6 A11y First & Agent Ready

```python
@app.status("msg", role="status", description="操作結果")
def msg():
    return "待機中"

# schema() で Agent/LLM 向け JSON を出力
print(app.schema())
# → {"title": "...", "widgets": [{"name": "msg", "kind": "status", "role": "status", ...}]}
```

---

## 2. セットアップ

```bash
cd nextpytk
uv sync --python 3.14
```

> 注: 一部の macOS 環境では `uv` の `3.14+freethreaded` で Tk 起動時に `Can't find a usable init.tcl` が発生します。
> 実行時に `PYTHON=...` を切り替えできます（例: `make run PYTHON=3.13` / `make run PYTHON=3.14+freethreaded` / `make run PYTHON=3.15`）。

---

## 3. レイアウトリファレンス

### 3.1 シンプルリスト

```python
app.run(layout=["title", "timer", "start", "status"])
```

各名前が1つの pack セクションになる。余剰 kwargs は `section()` に転送:

```python
Layout.from_list(["a", "b"], fill="both", expand=True)
```

### 3.2 Fluent DSL

**Pack セクション:**

```python
Layout().section("msg").section("phase", "count").section("start", "pause")
```

**Grid ビルダー:**

```python
from nextpytk.types import Sticky

Layout().grid()
  .span(2).widget("title", sticky=Sticky.W)
  .next_row()
  .widget("label", sticky=Sticky.RIGHT).widget("input", sticky=Sticky.LEFT_RIGHT)
  .next_row()
  .span(2).widget("ok")
.end_grid()
```

Grid builder メソッド:

| メソッド | 説明 |
|----------|------|
| `widget(name, *, sticky, padx, pady, colspan, rowspan)` | 現在位置に配置、列を進める |
| `span(cols)` | 次の `widget()` の列スパンを設定（1回限り） |
| `next_row()` | 次の行の先頭列へ |
| `next_col(n=1)` | n 列スキップ |
| `at(row, col)` | 絶対位置へジャンプ |
| `col_weights(*w)` | 列の重みを一括設定 |
| `row_weights(*w)` | 行の重みを一括設定 |
| `col_weight(col, w)` | 1列だけ重みを設定 |
| `row_weight(row, w)` | 1行だけ重みを設定 |
| `col_minsize(col, px)` | 列の最小幅 |
| `row_minsize(row, px)` | 行の最小高さ |
| `end_grid()` | grid ブロックを終了 |

### 3.3 With-block（コンテキストマネージャ）

```python
from nextpytk import LayoutBuilder

# スタンドアロン
builder = LayoutBuilder()
with builder:
    builder.section("title")
    with builder.grid(col_weights=(0, 1)):
        builder.widget("celsius", sticky="ew")
        builder.widget("fahrenheit", sticky="ew")
        builder.next_row().span(2).widget("note")
app.run(layout=builder.build())

# app.layout() ショートカット
with app.layout() as b:
    b.section("title")
    with b.grid(col_weights=(0, 1)):
        b.widget("celsius", sticky="ew")
app.run(layout=b.build())
```

`with b.grid(...)` は自動でクローズ。`end_grid()` 不要。

`grid()` に直接指定可能なオプション: `col_weights=(0,1)`, `row_weights=(...)`, `padx`, `pady`, `fill`, `expand`, `uniform`。

---

## 4. サンプル一覧

| ファイル | 内容 |
|----------|------|
| `examples/grid_temp.py` | grid レイアウト・温度変換 |
| `examples/task_panel.py` | 複数ラベル＋エントリ＋ボタンの状態管理 |
| `examples/multiscreen.py` | 画面遷移・注文アプリ |
| `examples/widget_gallery.py` | 全ウィジェット種別＋multiview によるタブ切替 |
| `examples/disk_usage_flat_viewer.py` | ディスク使用量フラットビューア（同期版、ncdu風） |
| `examples/disk_usage_flat_async.py` | ディスク使用量フラットビューア（非同期版、ncdu風） |

```bash
uv run python examples/grid_temp.py
uv run python examples/task_panel.py
uv run python examples/multiscreen.py
uv run python examples/widget_gallery.py
uv run python examples/disk_usage_flat_viewer.py
uv run python examples/disk_usage_flat_async.py
```

---

## 5. ウィジェット一覧

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

---

## 6. 型定数リファレンス

| 型 | 名前空間 | 例 |
|------|-----------|---------|
| `Side` | `Side.TOP/BOTTOM/LEFT/RIGHT` | pack side |
| `Fill` | `Fill.X/Y/BOTH/NONE` | pack fill |
| `Sticky` | `Sticky.NSEW/LEFT_RIGHT/TOP/BOTTOM/LEFT/RIGHT` | grid sticky |
| `State` | `State.NORMAL/DISABLED/ACTIVE` | widget state |
| `Orient` | `Orient.HORIZONTAL/VERTICAL` | scale orientation |
| `Relief` | `Relief.FLAT/RAISED/SUNKEN/GROOVE/RIDGE/SOLID` | border style |
| `Justify` | `Justify.LEFT/RIGHT/CENTER` | text alignment |
| `SelectMode` | `SelectMode.SINGLE/BROWSE/MULTIPLE/EXTENDED` | listbox mode |

---

## 7. 非同期 Native（asyncio + Tkinter）

```python
@app.job("scan")
async def scan(vals):
    result = await asyncio.to_thread(some_blocking_call)
    return {"status": "done"}

app.run_async(layout=Layout().section("status"))
```

---

## 8. 設計思想

### Web の三層構造との対応

| Web | nextpytk |
|-----|---------|
| HTML（マークアップ） | `@app.label(...)` / `@app.button(...)` によるウィジェット登録 |
| CSS（スタイル） | 将来: Tk option / ttk.Style を `Layout` 経由で注入 |
| JavaScript（インタラクション） | デコレータ付きコールバック関数 + `_apply_state` → `_sync_widgets` |

### 既存ライブラリとの関係

- **`tkinter`（標準）**: ベースとして尊重。nextpytk はその上に Decorator / Schema / A11y 層を載せる
- **`ttk`**: OS ネイティブな見た目と A11y を継承
- **`CustomTkinter`**: モダン L&F の先行事例。Canvas 描画が A11y 的に空白になる課題に対し、nextpytk は A11y を最初から組み込む
- **`TkRouter`** (israel-dryer, ttkbootstrap 作者): URL風パス・アニメーション遷移・履歴スタックによる宣言的ルーティング。nextpytk の `multiview` と補完関係（画面遷移 vs ウィジェット構築）

---

## 9. ライセンス

MIT License

## 10. 著者

西本卓也 (Takuya Nishimoto) — 株式会社シュアルタ
