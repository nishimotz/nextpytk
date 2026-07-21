# nextpytk

Python関数から、アクセシブルなTkinter GUIを宣言的に構築するライブラリ。

ウィジェット登録とレイアウトを分け、role / description などの意味構造を
一箇所で持てます。書き方は Flask 風のデコレータ。`schema()` で同じ構造を
エージェント向けにエクスポートできます。

---

## 1. コンセプト

### 1.1 デコレータ API

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

例えば、ヘッダー付きタブ UI を 1 行で書くこともできます:

```python
app.run(multiview="main", toplevel_widgets=["header"])
```

ビューレイアウトにもリストや with-block を使える。例えば
`view_layouts` の値はウィジェット名の単純なリストでもよい:

```python
view_layouts = {
    "Home": ["title", "start"],
    "Settings": ["timer", "status"],
}
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
@app.status("msg", description="操作結果")
def msg():
    return "待機中"

# schema() で Agent/LLM 向け JSON を出力
print(app.schema())
# → {"title": "...", "widgets": [{"name": "msg", "kind": "status", "role": "status", ...}]}
```

`role="status"` は schema / Tk accessible メタデータです。ARIA live region 相当の自動読み上げは未対応です。

ステータス文字を `font=` などで大きく表示する場合は `@app.status(..., font=("TkDefaultFont", 18, "bold"))` のように指定できます（`@app.label` と同じオプションを受け付けます）。

### 1.7 レイアウトデバッグ

ウィジェット構築後に `app.debug_layout()` を呼ぶと、登録ウィジェットごとの
geometry / pack・grid 情報を JSON 互換で返せます（クリップや minsize、
レイアウト回帰の調査向け。エージェントへの引き渡しにも使えます）。

```python
print(app.debug_layout())
# → {"title": "...", "sections": [{"widgets": [{"name": "msg", "geometry": ..., ...}, ...]}]}
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

layout = (
    Layout()
    .grid()
    .span(2).widget("title", sticky=Sticky.W)
    .next_row()
    .widget("label", sticky=Sticky.RIGHT).widget("input", sticky=Sticky.LEFT_RIGHT)
    .next_row()
    .span(2).widget("ok")
    .end_grid()
)
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

`grid()` に直接指定可能なオプション: `padx`, `pady`, `fill`, `expand`, `uniform`。

---

## 4. サンプル一覧

| ファイル | 内容 |
|----------|------|
| `examples/grid_temp.py` | grid レイアウト・温度変換 |
| `examples/task_panel.py` | 複数ラベル＋エントリ＋ボタンの状態管理 |
| `examples/multiscreen.py` | 画面遷移・注文アプリ |
| `examples/widget_gallery.py` | 全ウィジェット種別＋multiview によるタブ切替 |
| `examples/header_demo.py` | `Layout.header` / `.status` の chrome |
| `examples/combobox_demo.py` | ttk.Combobox |
| `examples/menubar_demo.py` | メニューバー |
| `examples/disk_usage_flat_async.py` | ディスク使用量フラットビューア（非同期版、ncdu風） |

```bash
uv run python examples/grid_temp.py
uv run python examples/task_panel.py
uv run python examples/multiscreen.py
uv run python examples/widget_gallery.py
uv run python examples/header_demo.py
uv run python examples/combobox_demo.py
uv run python examples/menubar_demo.py
uv run python examples/disk_usage_flat_async.py
```

---

## 5. ウィジェット一覧

| デコレータ | ウィジェット種別 | コールバック引数 | 返り値 |
|------------|------------------|------------------|--------|
| `@app.label(name, font=..., anchor=..., justify=..., padding=...)` | tk.Label | なし | `str` または `dict` |
| `@app.status(name)` | tk.Label（`role=status` メタデータ） | なし | `str` または `dict` |
| `@app.message(name, width=..., auto_width=...)` | tk.Label (wrap) | なし | `str` または `dict` |
| `@app.button(name, label=..., font=..., state=..., enabled_if=...)` | ttk.Button | `dict` (entry values) | `dict` (state update) |
| `@app.job(name)` | async callable | `dict` (entry values) | `dict` (state update) |
| `@app.entry(name, placeholder=..., show=..., font=..., padding=..., width=..., events=...)` | ttk.Entry | `str` (値) | `dict` (state update) |
| `@app.checkbutton(name, text=..., font=...)` | ttk.Checkbutton | `bool` | `dict` |
| `@app.radiobutton(name, text=..., value=..., group=..., font=...)` | ttk.Radiobutton | `str` (値) | `dict` |
| `@app.combobox(name, values=..., values_key=..., readonly=..., font=...)` | ttk.Combobox | `str` (値) | `dict` |
| `@app.menubar(name)` | tk.Menu（ウィンドウメニューバー） | なし | メニュー項目リスト |
| `@app.text(name, width=..., height=..., font=...)` | tk.Text | `str` (全内容) | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | `str` (値) | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=..., font=...)` | ttk.Spinbox | `str` (値) | `dict` |
| `@app.listbox(name, items=..., items_key=..., selectmode=..., font=..., events=...)` | tk.Listbox | `str` (選択項目) | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | なし | — |

`@app.status` は schema / accessible の `role="status"` メタデータを付けます。ARIA live region 相当の読み上げはまだ未対応です（次バージョン以降の課題）。操作結果のフィードバック向きで、高頻度のミラー表示には `@app.label` を使ってください。

`app.run(stages=..., tabposition=...)` と `@app.stages` で状態駆動の画面切替ができます。テーマヘルパー（`apply_theme` / `tokens` / layout chrome）はパッケージから import できます（`examples/header_demo.py` 参照）。

### テーマ

`TkApp` は `theme` パラメータを受け取ります。

| 値 | 意味 |
|----|----|
| `"kizashi"`（デフォルト） | 内蔵の Kizashi デザインシステムを適用 |
| `"none"` | ttk スタイルを変更しない（プラットフォームのデフォルトを使用） |
| 組み込みテーマ名（例: `"clam"`, `"vista"`, `"aqua"`） | Kizashi 上書きなしでその ttk テーマを使用 |

```python
# プラットフォームのデフォルト ttk テーマを使用
app = TkApp(title="Native", theme="none")

# 任意のインストール済み ttk テーマを使用
app = TkApp(title="Clam", theme="clam")
```

### 共通オプション

- `font`: `(family, size[, weight])` タプル。例: `font=("TkDefaultFont", 18, "bold")`
- `padding`: 内側の余白。整数または `(x, y)` / `(left, top, right, bottom)` タプル。例: `padding=4` または `padding=(4, 2)`

### label の拡張オプション

- `font`, `anchor`, `justify`, `padding`, `width`

### entry のオプション

- `placeholder`, `show`, `font`, `padding`, `width`, `state`
- `padding` は `height` に対応していない `ttk.Entry` の視覚的な高さを宣言的に増やす方法です。

### button / checkbutton / radiobutton / spinbox / combobox / listbox / text

- `font` を統一して受け付けます。ttk 系はテーマを継承した派生 style を内部で作成して適用するため、色やマップ・レイアウトなど他のテーマ属性は維持されます。

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
| `EventSeq` | `EventSeq.RETURN/ESCAPE/BACKSPACE/DELETE/TAB/...` | イベントシーケンス（binding 用） |
| `EventSeq` (マウス) | `EventSeq.BUTTON_1/2/3`, `DOUBLE_BUTTON_1/2/3`, `PRIMARY_DOUBLE_CLICK` | マウスイベントシーケンス |
| `EventSeq` (仮想) | `EventSeq.LISTBOX_SELECT/COMBOBOX_SELECTED/NOTEBOOK_TAB_CHANGED/...` | 仮想イベント |

### イベントシーケンス

`EventSeq` 定数を `events=` オプション（`@app.listbox` / `@app.entry`）で使います:

```python
from nextpytk.types import EventSeq

events={
    EventSeq.RETURN: lambda state: open_child(),
    EventSeq.PRIMARY_DOUBLE_CLICK: lambda state: open_child(),
    EventSeq.BACKSPACE: lambda state: go_parent(),
}
```

`EventSeq.PRIMARY_CLICK`, `EventSeq.PRIMARY_DOUBLE_CLICK`,
`EventSeq.PRIMARY_BUTTON_RELEASE` は a11y 対応の遅延デスクリプタで、
OS のプライマリマウスボタン設定（Windows/macOS/Linux の左右入れ替え）を
考慮したイベントシーケンスを返します。

### 動的選択肢

- `@app.listbox(..., items_key="results_items")` — 状態駆動のリスト内容。
  `apply_state({"results_items": ["a", "b", "c"]})` でリストを更新。
- `@app.combobox(..., values_key="folder_values")` — 状態駆動のドロップダウン値。
  `apply_state({"folder_values": ["INBOX", "Sent"]})` で選択肢を更新。

### entry ウィジェットレベルのイベント

`@app.entry(..., events={EventSeq.RETURN: handler})` でウィジェット固有の
イベントハンドラを登録。ハンドラは現在の entry values dict を受け取り、
state update dict を返します（button コールバックと同じシグネチャ）。

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
