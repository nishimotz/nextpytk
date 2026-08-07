# nextpytk

Python 関数から、アクセシブルな Tkinter GUI を宣言的に構築するライブラリ。

ウィジェットを普通の Python 関数として登録し、レイアウトは別に宣言し、
role / description を一箇所にまとめます。書き方は Flask 風のデコレータ。
`schema()` は登録ウィジェットの構造を JSON 互換でエクスポートできます。
利用可能な箇所では ttk ウィジェットを使います。

---

## Quick Start

まずは、ボタンが自分のラベルを書き換えるアプリを作ります。

```bash
pip install nextpytk
```

```python
from nextpytk import TkApp

app = TkApp(title="Hello")

@app.button("hello")
def on_hello():
    return "world"

app.run()
```

これだけで、`hello` と表示されたボタンのウィンドウが現れます。ボタンを押すと
ラベルが `world` に変わります。

---

## 動作の考え方

最小の例の中身を分解します。

```python
@app.button("hello")
```

`hello` という名前のボタンを登録します。`label=` を省略すると、ウィジェット名が
そのままボタンの文字になります。

```python
def on_hello():
    return "world"
```

ボタンを押すとこのコールバックが動きます。素の文字列を返すと、そのボタン自身の
ラベルが更新されます。これは `{"hello": "world"}` の糖衣構文です。

```python
app.run()
```

`layout=` を省略すると、登録済みのウィジェットが自動で1列に配置されるため、
シンプルなアプリではレイアウト宣言が不要です。

基本的な流れは次のとおりです。

* ウィジェットを名前で登録する
* コールバックから `dict`（または素の文字列）を返す
* `state` が更新され、対応するウィジェットへ反映される

---

## 入力した値を使う

次に、名前を入力して「あいさつ」ボタンを押すアプリへ変更します。

```python
from nextpytk import TkApp

app = TkApp(title="Hello")

@app.entry("name", placeholder="名前")
def on_name():
    return {}

@app.status("msg")
def msg():
    return "名前を入力してください"

@app.button("greet", label="あいさつ")
def on_greet(values):
    name = values["name"]
    return {"msg": f"こんにちは、{name}さん！"}

app.run(layout=["name", "greet", "msg"])
```

`entry` は入力欄を登録します。

```python
@app.entry("name", placeholder="名前")
```

ここでも `"name"` がウィジェット名です。変更時コールバックは必須なので、
ボタンからだけ読む場合は引数なしで空の `dict` を返しておけば十分です。

ボタンのコールバックでは、入力欄の現在値を `values` から取得できます。

```python
def on_greet(values):
    name = values["name"]
```

`values["name"]` は、`name` という名前で登録した `entry` の現在値です。

たとえば入力欄に

```text
Taro
```

と入力してボタンを押すと、コールバックは次の `dict` を返します。

```python
{"msg": "こんにちは、Taroさん！"}
```

この値が `state` にマージされ、`msg` という名前のステータス領域へ反映されます。

## `values` と `state`

ここで2種類の辞書が登場します。

* `values`
  コールバックを呼び出した時点の入力値

* `state`
  アプリ全体で共有される現在の状態

ボタンのコールバックでは、`values` を読んで処理し、変更したい状態を `dict` で返します。

```python
def on_greet(values):
    name = values["name"]
    return {"msg": f"こんにちは、{name}さん！"}
```

流れをまとめると次のようになります。

* `entry` へ入力する
* ボタンを押す
* `values` から入力値を読む
* コールバックが更新内容を `dict` で返す
* 返された内容が `state` にマージされる
* `state` の内容が対応するウィジェットへ反映される

この仕組みが nextpytk の基本的な状態更新モデルです。

---

## Design System

nextpytk は型付き定数とデザイントークンを同梱しています。生の tkinter 文字列や
マジックナンバーよりこちらを優先すると、アプリ間の一貫性と IDE 補完が得られます。

### Typed Constants

```python
from nextpytk.types import Side, Fill, Sticky, State, Orient

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
```

| 型 | 名前空間 | 例 |
|------|-----------|---------|
| `Side` | `Side.TOP/BOTTOM/LEFT/RIGHT` | pack side |
| `Fill` | `Fill.X/Y/BOTH/NONE` | pack fill |
| `Sticky` | `Sticky.NSEW/EW/NS/TOP/BOTTOM/LEFT/RIGHT` | grid sticky |
| `State` | `State.NORMAL/DISABLED/ACTIVE` | widget state |
| `Orient` | `Orient.HORIZONTAL/VERTICAL` | scale / paned orientation |
| `Relief` | `Relief.FLAT/RAISED/SUNKEN/...` | border style |
| `Justify` | `Justify.LEFT/RIGHT/CENTER` | text alignment |
| `Wrap` | `Wrap.WORD/NONE/CHAR` | text wrap mode |
| `SelectMode` | `SelectMode.SINGLE/BROWSE/MULTIPLE/EXTENDED` | listbox mode |
| `EventSeq` | `EventSeq.RETURN/ESCAPE/BACKSPACE/DELETE/TAB/...` | binding 用イベントシーケンス |
| `EventSeq` (マウス) | `EventSeq.BUTTON_1/2/3`, `DOUBLE_BUTTON_1/2/3`, `PRIMARY_DOUBLE_CLICK` | マウスイベント |
| `EventSeq` (仮想) | `EventSeq.LISTBOX_SELECT/COMBOBOX_SELECTED/NOTEBOOK_TAB_CHANGED/...` | 仮想イベント |

各型には対応する `*Like` Literal エイリアス（例: `FillLike`）があり、必要なら生文字列も使えます。

### Event sequences

`EventSeq` 定数を `events=` オプション（`@app.listbox` / `@app.entry`）で使います。
これらのハンドラは、ウィジェット本来の選択／変更コールバックとは **別物** です:

| API | ハンドラ引数 | 典型用途 |
|-----|--------------|----------|
| `@app.listbox` の選択コールバック | 選択 index `int`（未選択は `-1`） | 選択に反応 |
| `@app.listbox(..., events=...)` | 現在の **state** dict | Return / ダブルクリック / Backspace |
| `@app.entry` の変更コールバック | 値 `str` | 入力に反応 |
| `@app.entry(..., events=...)` | **entry values** dict（全 entry） | Return で送信（button と同型） |

```python
from nextpytk.types import EventSeq, SelectMode

@app.listbox(
    "results",
    items_key="results_items",
    selectmode=SelectMode.BROWSE,
    events={
        EventSeq.RETURN: lambda state: open_child(),
        EventSeq.PRIMARY_DOUBLE_CLICK: lambda state: open_child(),
        EventSeq.BACKSPACE: lambda state: go_parent(),
    },
)
def on_results_select(idx: int) -> dict:
    return {"status": f"selected:{idx}"}

@app.entry(
    "query",
    events={
        EventSeq.RETURN: lambda values: {
            "status": f"search:{(values.get('query') or '').strip()}"
        },
    },
)
def on_query(value: str) -> dict:
    return {}
```

`EventSeq.PRIMARY_CLICK`, `EventSeq.PRIMARY_DOUBLE_CLICK`,
`EventSeq.PRIMARY_BUTTON_RELEASE` は a11y 対応の遅延デスクリプタで、
OS のプライマリマウスボタン設定（Windows/macOS/Linux の左右入れ替え）を
考慮したイベントシーケンスを返します。

### Dynamic choices

状態駆動の選択肢は treeview の `rows_key` と同じ発想です。選択値は
`state[name]` / `state[key]` に置き、選択肢だけ別キーで更新します。

```python
@app.listbox("results", items_key="results_items")
def on_results_select(idx: int) -> dict:
    return {}

@app.combobox("folder", values_key="folder_values")
def on_folder(value: str) -> dict:
    return {}

# あとから（button / job / initial_state）:
app.apply_state({
    "results_items": ["a", "b", "c"],
    "folder_values": ["INBOX", "Sent"],
})
```

`items_key` / `values_key` を省略すると、静的な `items=` / `values=` のままです。

### Spacing tokens

```python
from nextpytk.tokens import SPACE

SPACE[1]  # 4px  — ウィジェット内の小さな余白
SPACE[2]  # 8px  — 隣接ウィジェット
SPACE[3]  # 12px — セクション内ギャップ
SPACE[4]  # 16px — セクション余白
SPACE[6]  # 24px — 大きなブロック
SPACE[8]  # 32px — ページ級ギャップ
```

基準は 4px 単位で、よく使う段階だけを提供しています。`padx` / `pady` や
ウィジェットの `padding` には、できる限り `SPACE[n]` を使ってください。

### Themes

`TkApp` は `theme` パラメータを受け取ります。

| 値 | 意味 |
|----|------|
| `"kizashi"`（デフォルト） | 内蔵の Kizashi デザインシステムを適用 |
| `"none"` | ttk スタイルを変更しない（プラットフォームのデフォルト） |
| 組み込みテーマ名（例: `"clam"`, `"vista"`, `"aqua"`） | Kizashi 上書きなしでその ttk テーマを使用 |

```python
# プラットフォームのデフォルト ttk テーマを使用
app = TkApp(title="Native", theme="none")

# 任意のインストール済み ttk テーマを使用
app = TkApp(title="Clam", theme="clam")
```

`Layout.header()` / `.status()` の chrome と `nextpytk.theme.apply_theme()` は
`examples/header_demo.py` を参照してください。

---

## Multiview (Multi-tab)

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

ビューレイアウトにもリストや with-block を使えます。例えば
`view_layouts` の値はウィジェット名の単純なリストでもよいです:

```python
view_layouts = {
    "Home": ["title", "start"],
    "Settings": ["timer", "status"],
}
```

---

## Layout DSL

3方式から目的に合わせて選べます:

```python
from nextpytk import Layout

# 1) シンプルリスト（一番おすすめ）
app.run(layout=["msg", "greet"])

# 2) Fluent DSL
app.run(layout=Layout().section("msg").section("greet"))

# 3) with-block（コンテキストマネージャ）
with app.layout() as b:
    b.section("msg")
    b.section("greet")
app.run(layout=b.build())
```

### Simple list

```python
app.run(layout=["title", "timer", "start", "status"])
```

各名前が1つの pack セクションになります。余剰 kwargs は `section()` に転送されます:

```python
Layout.from_list(["a", "b"], fill="both", expand=True)
```

### Layout spacing（レイアウト単位の間隔設定）

デフォルトのブロック余白はデザイントークン `SPACE[1]`（4 px）から取得されます。
`Layout` コンストラクタに `spacing=...` を渡すと、その Layout が作るすべてのブックで
使われるデフォルト余白を一括で変更できます:

```python
from nextpytk import tokens

layout = Layout(spacing=2).section("a").section("b").grid().widget("c").end_grid()
```

`spacing` は `nextpytk.tokens.SPACE` のキー（1, 2, 3, 4, 6, 8）を受け取り、
`section()` / `grid()` / `paned()` / grid の `widget()` / ネストフレーム におけるデフォルトの
`padx` / `pady` を決めます。メソッド呼び出しで明示的に `padx` / `pady` を指定した場合は
それが優先されます。

直接 `padx` / `pady` を指定することもできます:

```python
Layout(padx=tokens.SPACE[4], pady=tokens.SPACE[3]).section("a")
```

### Nested frames（ネストフレーム）

ひとつの `Layout` を名前付きフレームの中に入れ、視覚的なグループを作れます。
親子で pack/grid を混在させる問題を避け、内部は独立した Layout DSL で宣言できます。
内部の Layout は自分の spacing を持ち、pack セクション・grid・paned・さらなるネストフレームを
自由に使えます。

```python
inner = Layout().section("a", "b")
outer = Layout().section("title").frame("group", inner).section("ok")
app.run(layout=outer)
```

`frame(name, layout, side=..., fill=..., expand=..., padx=..., pady=...)` は
内部レイアウトを1つのブロックとして pack します。フレームは `name` として登録されるため、
grid のセル内に配置することも可能です:

```python
outer = (
    Layout()
    .grid()
    .widget("label")
    .widget("group", sticky="nsew")
    .end_grid()
    .frame("group", Layout().section("a", "b"))
)
```

### Paired レイアウト

`Layout.paired(left, right, ...)` は2つのウィジェットを1つの2列フレームに
左右に並べます。`app.paned` より軽量な diff/compare ビュー向けの選択肢です:

```python
layout = (
    Layout()
    .section("info")
    .paired(
        "left_text",
        "right_text",
        weight=(1, 1),
        fill=Fill.BOTH,
        expand=True,
        sync_yscroll=True,
    )
)
```

オプション:

| 引数 | 既定値 | 説明 |
|----------|---------|-------------|
| `weight` | `(1, 1)` | 2列の `(左, 右)` 重み |
| `fill` | `"x"` | フレームの `pack fill` |
| `expand` | `False` | フレームの `pack expand` |
| `sync_yscroll` | `False` | 2つのウィジェットの y-scroll コマンドを相互接続 |
| `line_numbers` | `False` | 両側に読み取り専用の行番号ガターを追加 |
| `side`, `padx`, `pady`, `anchor` | — | 通常の Layout ブロック配置オプション |

`sync_yscroll=True` で、両方が `@app.text` ウィジェットの場合、どちらかを
スクロールするともう一方も追従します。同じ効果はウィジェットごとに
`@app.text(..., sync_yscroll_with="other")` で得られますが、paired レイアウトは
ウィジェット宣言を変更せずにレイアウトレベルでその接続を提供します。

`line_numbers=True` にすると、各側に読み取り専用の行番号ガターが付きます。
両ペインと両ガターが**単一の垂直スクロールバー**を共有するため、ガターは
コンテンツと常に同期します（ずれません）。論理行番号（`1..n`）はペインの
内容に追従し、右ペインを編集すると番号も更新されます。

> **注:** `line_numbers=True` は `sync_yscroll` より優先されます。この設定が
> 導入する共有スクロールバーは両ペイン（と両ガター）を常に同期させるため、
> `sync_yscroll=False` を `line_numbers=True` と一緒に指定しても効果はありま
> せん。ペインを独立してスクロールさせたい場合は `line_numbers` をオフにして
> ください。

### Wrap レイアウト

`Layout.wrap()` は折り返しフローです（Flutter の `Wrap` に相当）。各ウィジェットを
列いっぱいに伸ばさず、内容や `width=` で決まる幅のまま左から右へ並べ、次の
ウィジェットが残り幅に収まらなくなったら自動的に次の行へ折り返します。同じ行に
並ぶ widget は上下方向を中央揃えし、たとえば高い `entry` と低い `button` や
`checkbutton` が midline で揃います。gap はレイアウトの spacing を既定値として
継承します（`gapx`/`gapy` で個別に上書きできます）。

```python
TAGS = ["python", "tkinter", "async", "uv", "type hints"]
for tag in TAGS:
    @app.button(tag, label=f"#{tag}")
    def on_tag(values, tag=tag):
        return {"msg": f"Selected: {tag}"}

app.run(layout=Layout(spacing=2).status("msg").wrap(*TAGS))
```

Wrap はタグクラウド、ツールバー、フィルター UI などに向いています。
ウィンドウをリサイズすると行が自動的に再計算されます。`gapx`/`gapy` で間隔を
上書き、`side`/`fill`/`expand` で wrap フレームの pack 動作を制御できます。

`Flex(name, flex=...)` で包んだ子は、その行の余剰幅を吸収します
（Flutter の `Expanded` に相当）:

```python
from nextpytk import Flex

app.run(layout=Layout().wrap("filter", Flex("search", flex=2), "ok", gapx=2))
```

カスタム配置が必要なら `Layout.flow()` に `FlowDelegate`（Flutter の `Flow` に
相当）を渡し、利用可能な `Constraints` から各子の `(x, y, width, height)` を計算
させます。`Flex` と `Flow` の使い方は `examples/wrap_demo.py` を参照してください。

**動作の仕組み。** `wrap` と `flow` は子を `place`（x/y 絶対指定）で配置します。
`pack -side left` ではみ出した子が画面外に消えるだけのため、`pack` では次の行へ
折り返せないからです。`place` である以上、以下の制約があります:

- すべての子は 1 つの親フレームに `place` で配置されます。同じ親に対して
  `pack`/`grid` と混在させることはできません（混ぜると `TclError: conflicting
  geometry managers`）。
- 幅は `winfo_reqwidth()` から算出し、フレームは `pack_propagate(False)` で
  高さを明示します。
- リサイズ時は再計算され、行が新しい幅に合わせて折り返します。

`place` は Tk のネイティブな Tab 巡回（pack/grid の挿入順に基づく）を迂回するため、
`wrap` は `<Tab>`/`<Shift-Tab>` を捕捉して視覚的な行優先順でフォーカスを移動
させます。`Entry`/`Text` の子は Tab 入力を残すためスキップされ、先頭と末尾で
折り返します。

### 動的領域切り替え（swap target）

`Layout.target()` は実行時に中身を差し替えられる領域を予約します（HTMX の
`hx-target` / `hx-swap` に相当）。周囲の section（ツールバーやステータス）は
固定したまま、target 領域だけを入れ替えます:

```python
layout = Layout().wrap("go_dir", "go_file", "info").target("main_area")

@app.swap(
    "main_area",
    variants={
        "dir":  [Layout().section("dir_tree")],
        "file": [Layout().paired("left_text", "right_text",
                                 fill=Fill.BOTH, expand=True)],
    },
    default="dir",
)
def main_area():
    pass

# 実行時に命令的に切り替え:
app.swap_view("main_area", "file")
```

`@app.swap` の variants は起動時にマウントされ、pack の表示/非表示で切り替わります。
そのためツリービューの選択やスクロール位置などのウィジェット状態は切替をまたいで
保持されます。各 variant は `Layout` またはウィジェット名のリストです。
`examples/swap_demo.py` を参照してください。

### ウィジェットの表示 / 非表示

単一ウィジェットを実行時に条件付きで出し分けたい場合に、`app.hide(name)` /
`app.show(name)` を使います:

```python
if should_show:
    app.show("code")   # 元の grid セル / pack 位置に復元
else:
    app.hide("code")   # レイアウト情報を失わずに取り除く
```

- `app.hide(name)` はウィジェットを section から外し（`grid_remove` /
  `pack_forget`）、記録しておくため、後続の `apply_state` / `sync` で再配置
  されません。
- `app.show(name)` は元の grid セル / pack オプションの位置に復元します。
- `app.is_visible(name)` はウィジェットが現在マップされているかを返します。
- `app.set_padding(name, padx=..., pady=...)` はレイアウトのパディングを動的
  に変更します。これは **非表示対応（hide-aware）** で、ウィジェットが隠れて
  いる間は変更を記憶し、`show()` で復元するときに反映します。`pack_forget`
  済みのウィジェットへ `pack_configure` を呼ぶと（黙って再表示されてしまう
  ため）そうはせずに、非表示を維持したままパディングを更新できます。
- いずれも既に隠れている / 表示されているウィジェットや、まだ構築前の
  ウィジェットに対して安全に呼べます。

### Fluent DSL

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
| `widget(name, *, sticky, padx, pady, colspan, rowspan)` | 現在位置に配置し、列を進める |
| `span(n)` | 次の `widget()` の列スパンを設定 |
| `next_row()` | 次の行へ移り、列をリセット |
| `next_col(n)` | n 列スキップ |
| `at(row, col)` | 絶対位置へジャンプ |
| `col_weight(col, w)` | 1列だけ重みを設定 |
| `row_weight(row, w)` | 1行だけ重みを設定 |
| `col_minsize(col, px)` | 列の最小幅 |
| `row_minsize(row, px)` | 行の最小高さ |
| `end_grid()` | Layout チェーンへ戻る |

`col_weight(0, 0).col_weight(1, 1)` で列 0 → weight 0、列 1 → weight 1 と
明示できます。

### With-block (context manager)

```python
from nextpytk import LayoutBuilder

# スタンドアロン
builder = LayoutBuilder()
with builder:
    builder.section("title")
    with builder.grid():
        builder.col_weight(0, 0).col_weight(1, 1)
        builder.widget("celsius", sticky="ew")
        builder.widget("fahrenheit", sticky="ew")
        builder.next_row().span(2).widget("note")
app.run(layout=builder.build())

# app.layout() ショートカット
with app.layout() as b:
    b.section("title")
    with b.grid():
        b.col_weight(0, 0).col_weight(1, 1)
        b.widget("celsius", sticky="ew")
app.run(layout=b.build())
```

`with b.grid(...)` は自動でクローズします。`end_grid()` は不要です。

`grid()` に直接指定可能なオプション: `padx`, `pady`, `fill`, `expand`, `uniform`。

---

## Widget Reference

| デコレータ | ウィジェット | コールバック引数 | 返り値 |
|------------|--------------|------------------|--------|
| `@app.label(name, font=..., anchor=..., justify=..., padding=...)` | tk.Label | — | `str` または `dict` |
| `@app.status(name)` | tk.Label（`role=status` メタデータ） | — | `str` または `dict` |
| `@app.message(name, width=..., auto_width=...)` | tk.Label（自動ラップ） | — | `str` または `dict` |
| `@app.button(name, label=..., font=..., enabled_if=...)` | ttk.Button | entry values `dict` | `dict` |
| `@app.job(name)` | async callable | entry values `dict` | `dict` |
| `@app.entry(name, placeholder=..., show=..., font=..., padding=..., width=..., events=...)` | ttk.Entry | `str` | `dict` |
| `@app.checkbutton(name, text=..., font=...)` | ttk.Checkbutton | `bool` | `dict` |
| `@app.radiobutton(name, text=..., value=..., group=..., font=...)` | ttk.Radiobutton | 選択値 `str` | `dict` |
| `@app.combobox(name, values=..., values_key=..., readonly=..., font=...)` | ttk.Combobox | 選択値 `str` | `dict` |
| `@app.menubar(name)` | tk.Menu（ウィンドウメニューバー） | — | メニュー項目リスト |
| `@app.filepicker(name, mode=..., label=..., title=..., filetypes=..., ...)` | ttk.Button → tkinter.filedialog | 選択パス `str`, `list[str]`, または `None` | `dict` |
| `@app.text(name, width=..., height=..., font=..., wrap=..., h_scroll=..., scrollbar=...)` | tk.Text | 全内容 `str` | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | 値 `str` | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=..., font=...)` | ttk.Spinbox | 値 `str` | `dict` |
| `@app.listbox(name, items=..., items_key=..., selectmode=..., font=..., events=...)` | tk.Listbox | 選択 index `int`（未選択は `-1`） | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | — | — |

`@app.status` は schema / accessible の `role="status"` メタデータを付けます。ARIA live region 相当の読み上げはまだ未対応です（後続リリース予定）。操作結果のフィードバック向きで、静的・高頻度のミラー表示には `@app.label` を使ってください。

### ファイルピッカー

`@app.filepicker` はクリックで tkinter のファイルダイアログを開くボタンを作ります。
選択されたパスがコールバックに渡され、キャンセル時は `None` になります。

```python
@app.filepicker("open_file", mode="open", label="ファイルを開く",
                title="ファイルを開く", filetypes=[("テキストファイル", "*.txt")])
def pick_open_file(path: str | None) -> dict[str, Any]:
    return {"open_path": path}
```

モード: `"open"`（既定）, `"open_multiple"`, `"save"`, `"directory"`。

filepicker はメニューバーからも呼び出せます。`command` に filepicker 名を指定するだけです：

```python
@app.filepicker("m_open", mode="open", title="ファイルを開く")
def m_open(path):
    return {"open_path": path}

@app.menubar("menu")
def menu_bar():
    return [{"label": "ファイル", "items": [
        {"label": "開く...", "command": "m_open"},
    ]}]
```

`app.run(stages=..., tabposition=...)` と `@app.stages` で状態駆動の画面切替ができます。テーマヘルパー（`apply_theme` / `tokens` / layout chrome）はパッケージから import できます（`examples/header_demo.py` 参照）。

共通オプション:
- `font`: `(family, size[, weight])` タプル。例: `font=("TkDefaultFont", 18, "bold")`
- `padding`: 内側の余白。整数または `(x, y)` / `(left, top, right, bottom)` タプル。例: `padding=4` または `padding=(4, 2)`

label のオプション: `font`, `anchor`, `justify`, `padding`, `width`。

entry のオプション: `placeholder`, `show`, `font`, `padding`, `width`, `state`。
- `padding` は `height` を持たない `ttk.Entry` の視覚的な高さを宣言的に増やす方法です。

button / checkbutton / radiobutton / spinbox / combobox / listbox / text:
- `font` を統一して受け付けます。ttk 系はテーマを継承した派生 style を内部で作成するため、色やマップ・レイアウトなど他のテーマ属性は維持されます。

text の追加オプション:
- `wrap`: `Wrap.WORD`（デフォルト）/ `Wrap.NONE` / `Wrap.CHAR`。`Wrap.NONE` は各論理行を1行に保ちます。
- `h_scroll`: `True` にすると水平スクロールバーを追加します（`xscrollcommand` に接続）。通常は `wrap=Wrap.NONE` と組み合わせて長い行にアクセスします。
- `scrollbar`: `False` にすると垂直スクロールバーを省略します。テキストウィジェット自体は構築され使い続けられます（`text_set` / `text_get` で読み書き可能）が、プレーンな表示になります。枠線のないコード表示などに向いています。

すべてのウィジェットデコレータは `widget_kwargs: dict` も受け付け、構築後に
ウィジェット単位でデザイントークンを上書きできます。キーはウィジェット
ネイティブの tk/ttk オプション（`padx`, `pady`, `bg`, `fg`, `font`, …）です。
無効・未知のキーはビルドを中断せず無視されます。

```python
@app.text("log", wrap="none", h_scroll=True,
          widget_kwargs={"bg": "#1e1e1e", "fg": "#dcdcdc"})
def log(value): return {}
```

実行時アクセス: `app.text_widget(name)` は実体の `tk.Text` を返します。
`app.layout_frame(name)` はウィジェットを所有するレイアウト section フレームを
返します（手動 grid/pack 配置や再ペアレント用）。
`app.on_text_set(name, hook)` は、テキストウィジェットの内容が置き換えられた
後に実行するコールバックを登録します（paired の行番号ガターで使用）。

enum 系のオプション（`wrap`, `state`, `orient`, `selectmode`, `mode`）は
登録時に検証されます。不正な値は、ウィジェット構築時の `TclError` ではなく
明確な `ValueError`（オプション名と許可値を明記）を即座に発生させます。

`@app.message` は自動ラップのラベルです。`width` は初期ピクセル幅、`auto_width=True`（デフォルト）は親コンテナのリサイズに追従します。

---

## Typed Constants

```python
from nextpytk.types import Side, Fill, Sticky, State, Orient

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
```

値は tkinter 互換の `str` リテラルです。`SideLike` / `FillLike` などは生文字列も受け付けます。

| 型 | 名前空間 | 例 |
|------|-----------|---------|
| `Side` | `Side.TOP/BOTTOM/LEFT/RIGHT` | pack side |
| `Fill` | `Fill.X/Y/BOTH/NONE` | pack fill |
| `Sticky` | `Sticky.NSEW/LEFT_RIGHT/TOP/BOTTOM/LEFT/RIGHT` | grid sticky |
| `State` | `State.NORMAL/DISABLED/ACTIVE` | widget state |
| `Orient` | `Orient.HORIZONTAL/VERTICAL` | scale orientation |
| `Relief` | `Relief.FLAT/RAISED/SUNKEN/GROOVE/RIDGE/SOLID` | border style |
| `Justify` | `Justify.LEFT/RIGHT/CENTER` | text alignment |
| `Wrap` | `Wrap.WORD/NONE/CHAR` | text wrap mode |
| `SelectMode` | `SelectMode.SINGLE/BROWSE/MULTIPLE/EXTENDED` | listbox mode |
| `EventSeq` | `EventSeq.RETURN/ESCAPE/BACKSPACE/DELETE/TAB/...` | binding 用イベントシーケンス |
| `EventSeq` (マウス) | `EventSeq.BUTTON_1/2/3`, `DOUBLE_BUTTON_1/2/3`, `PRIMARY_DOUBLE_CLICK` | マウスイベント |
| `EventSeq` (仮想) | `EventSeq.LISTBOX_SELECT/COMBOBOX_SELECTED/NOTEBOOK_TAB_CHANGED/...` | 仮想イベント |

---

## Schema Export

`app.schema()` は登録ウィジェットのスナップショットを JSON 互換で返します
（`name` / `kind` / `label` / `role` / `description`、および種別固有のフィールド）。

```python
@app.label("temperature")
def t():
    return "25°C"

app.schema()
# → {"title": "...", "widgets": [{"name": "temperature", "kind": "label", ...}]}
```

---

## Layout debug

ウィジェット構築後に `app.debug_layout()` を呼ぶと、登録ウィジェットごとの
geometry / pack・grid 情報を JSON 互換で返せます（クリップや minsize、
レイアウト回帰の調査向け）。`run()` が終了した後でも安全に呼べます。
ウィンドウを閉じると Tk インタープリタが破棄されますが、
`debug_layout()` は破棄済みウィジェットでクラッシュせず
`"alive": False` と空の `sections`/`conflicts` を返します。

```python
app.run(layout=["msg", "go"])  # またはテスト / カスタム runner
print(app.debug_layout())
# → {"title": "...", "alive": True, "sections": [{"widgets": [{"name": "msg", "geometry": ..., ...}, ...]}]}
```

**ジオメトリマネージャー混在の検出。** `pack`/`grid`/`place` の混在（例: `wrap`/`flow`
が使う `place` フレームに手動で `pack`/`grid` を混ぜる）は文法では完全に防げないため、
`app.check_layout_conflicts()` がウィジェットツリーを検査して混在を報告します。
`TclError: conflicting geometry managers` を待たずに検出できます:

```python
print(app.check_layout_conflicts())
# → 混在があれば [{"master_class": "Frame", "managers": ["pack", "place"], ...}]
#    （各混在に対して warning も発せられます）
```

---

## Async-Native (asyncio + Tkinter)

`app.run_async()` は asyncio イベントループ上でアプリを動かし、
`root.tk.dooneevent(0)` で Tk メインループと協調スケジューリングします。
`app.spawn(coro)` は GUI 実行中に非同期タスクをスケジュールします。
`@app.job(name)` は async 呼び出しを登録します。

```python
@app.job("scan")
async def scan(vals):
    result = await asyncio.to_thread(some_blocking_call)
    return {"status": "done"}

app.run_async(layout=Layout().section("status"))
```

## Examples

```bash
uv run python examples/grid_temp.py          # 温度変換
uv run python examples/task_panel.py          # 複数ボタンのパネル
uv run python examples/multiscreen.py         # 画面遷移の注文アプリ
uv run python examples/widget_gallery.py      # 全ウィジェット種別
uv run python examples/header_demo.py         # Layout.header / .status chrome
uv run python examples/combobox_demo.py       # ttk.Combobox
uv run python examples/menubar_demo.py        # メニューバー
uv run python examples/filepicker_demo.py     # ファイルピッカー
uv run python examples/disk_usage_flat_async.py       # ncdu風ビューア（非同期）
uv run python examples/paired_demo.py           # 左右ペアレイアウト + y-scroll 同期
uv run python examples/swap_demo.py             # 動的領域切り替え（Layout.target + @app.swap）
uv run python examples/bottom_bar_demo.py       # 下部固定バー（section side="bottom"）
uv run python examples/live_validation.py       # ライブ検証（Tcl変数 trace 取り込み / ingest_trace=True）
```

---

## Requirements

- Python 3.13+（`requires-python`。サンプルは `Makefile` の `PYTHON=...` で既定 3.14）
- Python ビルドに Tkinter サポートがあること
- その他の依存なし

> 注: 一部の macOS 環境では `uv` の `3.14+freethreaded` で Tk 起動時に `Can't find a usable init.tcl` が発生します。
> 実行時に `PYTHON=...` を切り替えできます（例: `make run PYTHON=3.13` / `make run PYTHON=3.14+freethreaded` / `make run PYTHON=3.15`）。

---

## Related Projects

- **`tkinter`（標準）**: nextpytk の土台。その上に Decorator / Schema / A11y 層を載せます。
- **`ttk`**: OS ネイティブな見た目とアクセシビリティ。nextpytk は可能な限り ttk を使います。
- **`CustomTkinter`**: Canvas 描画によるモダンな見た目。nextpytk は逆にネイティブウィジェットと初期からの A11y を選びます。
- **`TkRouter`** (israel-dryer, ttkbootstrap 作者): URL 風パス・アニメーション遷移・履歴スタックによる宣言的ルーティング。nextpytk の `multiview` と補完関係（画面遷移 vs ウィジェット構築）。

## Changelog

変更履歴は [CHANGES.md](./CHANGES.md) を参照してください。

## License

MIT

## Author

西本卓也 (Takuya Nishimoto) — 株式会社シュアルタ
