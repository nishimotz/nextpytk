# nextpytk

Accessible, declarative Tkinter applications from ordinary Python functions.

Register widgets as plain Python functions, declare layout separately, and
keep roles/descriptions in one place. The decorator style is Flask-inspired;
`schema()` exports the registered widget structure as JSON-compatible data.
Uses ttk widgets where available.

---

## Quick Start

Start with an app where a button updates a message.

```bash
pip install nextpytk
```

```python
from nextpytk import TkApp

app = TkApp(title="Hello")

@app.status("msg")
def msg():
    return "Hello, world!"

@app.button("greet", label="Greet")
def on_greet():
    return {"msg": "Button clicked!"}

app.run(layout=["msg", "greet"])
```

---

## How it works

In nextpytk you register widgets by name and declare layout separately.

This example registers two widgets: `msg` and `greet`.

```python
@app.status("msg")
```

`msg` is a status area that shows a message.

```python
@app.button("greet", label="Greet")
```

`greet` is a button labeled "Greet".

Finally, name the display order:

```python
app.run(layout=["msg", "greet"])
```

When you press the button, the callback returns this `dict`:

```python
{"msg": "Button clicked!"}
```

nextpytk merges that into the app `state`.

Because `msg` is the name of the registered status area, its text becomes
"Button clicked!".

So the basic flow is:

* Register widgets by name
* List those names in the layout
* Return a `dict` from a callback
* `state` updates and matching widgets refresh

---

## Using input values

Next, change the app so you type a name and press Greet.

```python
from nextpytk import TkApp

app = TkApp(title="Hello")

@app.entry("name", placeholder="Name")
def on_name():
    return {}

@app.status("msg")
def msg():
    return "Enter your name"

@app.button("greet", label="Greet")
def on_greet(values):
    name = values["name"]
    return {"msg": f"Hello, {name}!"}

app.run(layout=["name", "greet", "msg"])
```

`entry` registers a text field.

```python
@app.entry("name", placeholder="Name")
```

Again, `"name"` is the widget name. An on-change callback is required; if you
only read the field from a button, a no-arg callback that returns `{}` is enough.

In the button callback, read the current field value from `values`:

```python
def on_greet(values):
    name = values["name"]
```

`values["name"]` is the current value of the `entry` registered as `name`.

For example, if you type

```text
Taro
```

and press the button, the callback returns:

```python
{"msg": "Hello, Taro!"}
```

That dict merges into `state` and updates the status area named `msg`.

## `values` and `state`

Two dictionaries appear here:

* `values`
  Input values at the moment the callback runs

* `state`
  Shared current state for the whole app

A button callback reads `values`, then returns a `dict` of state changes:

```python
def on_greet(values):
    name = values["name"]
    return {"msg": f"Hello, {name}!"}
```

The flow is:

* Type into an `entry`
* Press the button
* Read input from `values`
* Return updates as a `dict`
* Those updates merge into `state`
* Matching widgets refresh from `state`

That is nextpytk's basic state-update model.

---

## Design System

nextpytk ships with typed constants and design tokens. Prefer them over raw tkinter strings and magic numbers so every app stays consistent and IDE completion works out of the box.

### Typed Constants

```python
from nextpytk.types import Side, Fill, Sticky, State, Orient

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
```

| Type | Namespace | Example |
|------|-----------|---------|
| `Side` | `Side.TOP/BOTTOM/LEFT/RIGHT` | pack side |
| `Fill` | `Fill.X/Y/BOTH/NONE` | pack fill |
| `Sticky` | `Sticky.NSEW/EW/NS/TOP/BOTTOM/LEFT/RIGHT` | grid sticky |
| `State` | `State.NORMAL/DISABLED/ACTIVE` | widget state |
| `Orient` | `Orient.HORIZONTAL/VERTICAL` | scale / paned orientation |
| `Relief` | `Relief.FLAT/RAISED/SUNKEN/...` | border style |
| `Justify` | `Justify.LEFT/RIGHT/CENTER` | text alignment |
| `SelectMode` | `SelectMode.SINGLE/BROWSE/MULTIPLE/EXTENDED` | listbox mode |
| `EventSeq` | `EventSeq.RETURN/ESCAPE/BACKSPACE/DELETE/TAB/...` | event sequences for bindings |
| `EventSeq` (mouse) | `EventSeq.BUTTON_1/2/3`, `DOUBLE_BUTTON_1/2/3`, `PRIMARY_DOUBLE_CLICK` | mouse event sequences |
| `EventSeq` (virtual) | `EventSeq.LISTBOX_SELECT/COMBOBOX_SELECTED/NOTEBOOK_TAB_CHANGED/...` | virtual events |

Each type has a matching `*Like` literal alias (e.g. `FillLike`), so raw strings still work when needed.

### Event sequences

Use `EventSeq` constants for widget-level event bindings (`events=` on
`@app.listbox` and `@app.entry`). These handlers are **separate from** the
widget's select/change callback:

| API | Handler argument | Typical use |
|-----|------------------|-------------|
| `@app.listbox` select callback | selected index `int` (`-1` if none) | react to selection |
| `@app.listbox(..., events=...)` | current **state** dict | Return / double-click / Backspace |
| `@app.entry` change callback | value `str` | react to typing |
| `@app.entry(..., events=...)` | **entry values** dict (all entries) | Return to submit, like a button |

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

`EventSeq.PRIMARY_CLICK`, `EventSeq.PRIMARY_DOUBLE_CLICK`, and
`EventSeq.PRIMARY_BUTTON_RELEASE` are a11y-aware lazy descriptors that
return the event sequence for the OS-configured primary mouse button
(accounting for left/right button swap on Windows, macOS, and Linux/GNOME).

### Dynamic choices

State-driven choices mirror treeview's `rows_key`: keep the selection in
`state[name]` / `state[key]`, and refresh the options via a separate key.

```python
@app.listbox("results", items_key="results_items")
def on_results_select(idx: int) -> dict:
    return {}

@app.combobox("folder", values_key="folder_values")
def on_folder(value: str) -> dict:
    return {}

# Later (button, job, or initial_state):
app.apply_state({
    "results_items": ["a", "b", "c"],
    "folder_values": ["INBOX", "Sent"],
})
```

Omit `items_key` / `values_key` to keep a static `items=` / `values=` list.
### Spacing tokens

```python
from nextpytk.tokens import SPACE

SPACE[1]  # 4px  — small padding inside a widget
SPACE[2]  # 8px  — adjacent widgets
SPACE[3]  # 12px — section inner gaps
SPACE[4]  # 16px — section margins
SPACE[6]  # 24px — large blocks
SPACE[8]  # 32px — page-level gaps
```

The scale is based on a 4px unit and only common steps are provided. Use `SPACE[n]` for every `padx`/`pady` value and for widget-level `padding` values where practical.

### Themes

`TkApp` accepts a `theme` parameter:

| Value | Meaning |
|-------|---------|
| `"kizashi"` (default) | Apply the built-in Kizashi design system |
| `"none"` | Do not touch ttk styles; use the platform default theme |
| any built-in name (e.g. `"clam"`, `"vista"`, `"aqua"`) | Switch to that ttk theme without Kizashi overrides |

```python
# Use the platform default ttk theme
app = TkApp(title="Native", theme="none")

# Use any installed ttk theme
app = TkApp(title="Clam", theme="clam")
```

See `examples/header_demo.py` for `Layout.header()` / `.status()` chrome and `nextpytk.theme.apply_theme()` usage.

---

## Multiview (Multi-tab)

```python
from nextpytk import TkApp, Layout

app = TkApp(title="Multi-tab App")

@app.status("header")
def header(): return "Common header"

with app.view("Tab1", layout=Layout().section("t1_label", "t1_btn")) as v:
    @v.label("t1_label")
    def t1_label(): return "Tab 1 content"
    @v.button("t1_btn", label="Click")
    def t1_btn(vals): return {}

with app.view("Tab2", layout=Layout().section("t2_label")) as v:
    @v.label("t2_label")
    def t2_label(): return "Tab 2 content"

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

View layouts also accept lists or with-block builders. For example,
`view_layouts` values may be simple widget-name lists:

```python
view_layouts = {
    "Home": ["title", "start"],
    "Settings": ["timer", "status"],
}
```

---

## Layout DSL

Three styles — pick the one that fits:

```python
from nextpytk import Layout

# 1) Simple list (easiest)
app.run(layout=["msg", "greet"])

# 2) Fluent DSL
app.run(layout=Layout().section("msg").section("greet"))

# 3) with-block (context manager)
with app.layout() as b:
    b.section("msg")
    b.section("greet")
app.run(layout=b.build())
```

### Simple list

```python
app.run(layout=["title", "timer", "start", "status"])
```

Each name gets its own pack-based section. Extra kwargs forwarded to `section()`:

```python
Layout.from_list(["a", "b"], fill="both", expand=True)
```

### Fluent DSL

**Pack sections:**

```python
Layout().section("msg").section("phase", "count").section("start", "pause")
```

**Grid builder:**

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

Grid builder methods:

| Method | Description |
|--------|-------------|
| `widget(name, *, sticky, padx, pady, colspan, rowspan)` | Place widget at cursor, advance column |
| `span(n)` | Set colspan for the next `widget()` call |
| `next_row()` | Move to next row, reset column |
| `next_col(n)` | Skip n columns |
| `at(row, col)` | Jump to absolute position |
| `col_weight(col, w)` | Set a single column weight |
| `row_weight(row, w)` | Set a single row weight |
| `col_minsize(col, px)` | Column minimum width |
| `row_minsize(row, px)` | Row minimum height |
| `end_grid()` | Return to Layout chain |

Use `col_weight(0, 0).col_weight(1, 1)` to set column 0 → weight 0 and column 1 → weight 1.

### With-block (context manager)

```python
from nextpytk import LayoutBuilder

# Standalone builder
builder = LayoutBuilder()
with builder:
    builder.section("title")
    with builder.grid():
        builder.col_weight(0, 0).col_weight(1, 1)
        builder.widget("celsius", sticky="ew")
        builder.widget("fahrenheit", sticky="ew")
        builder.next_row().span(2).widget("note")
app.run(layout=builder.build())

# Via app.layout() shortcut
with app.layout() as b:
    b.section("title")
    with b.grid():
        b.col_weight(0, 0).col_weight(1, 1)
        b.widget("celsius", sticky="ew")
app.run(layout=b.build())
```

`with b.grid(...)` auto-closes — no `end_grid()` needed.

`grid()` options available directly: `padx`, `pady`, `fill`, `expand`, `uniform`.

---

## Widget Reference

| Decorator | Widget | Callback receives | Returns |
|-----------|--------|-------------------|---------|
| `@app.label(name, font=..., anchor=..., justify=..., padding=...)` | tk.Label | — | `str` or `dict` |
| `@app.status(name)` | tk.Label (`role=status` metadata) | — | `str` or `dict` |
| `@app.message(name, width=..., auto_width=...)` | tk.Label (auto-wrap) | — | `str` or `dict` |
| `@app.button(name, label=..., font=..., enabled_if=...)` | ttk.Button | entry values `dict` | `dict` |
| `@app.job(name)` | async callable | entry values `dict` | `dict` |
| `@app.entry(name, placeholder=..., show=..., font=..., padding=..., width=..., events=...)` | ttk.Entry | `str` | `dict` |
| `@app.checkbutton(name, text=..., font=...)` | ttk.Checkbutton | `bool` | `dict` |
| `@app.radiobutton(name, text=..., value=..., group=..., font=...)` | ttk.Radiobutton | selected value `str` | `dict` |
| `@app.combobox(name, values=..., values_key=..., readonly=..., font=...)` | ttk.Combobox | selected value `str` | `dict` |
| `@app.menubar(name)` | tk.Menu (window menubar) | — | menu item list |
| `@app.text(name, width=..., height=..., font=...)` | tk.Text | full content `str` | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | value `str` | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=..., font=...)` | ttk.Spinbox | value `str` | `dict` |
| `@app.listbox(name, items=..., items_key=..., selectmode=..., font=..., events=...)` | tk.Listbox | selected index `int` (`-1` if none) | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | — | — |

`@app.status` sets schema / accessible `role="status"` metadata. It is **not** an ARIA live region yet (planned for a later release). Prefer it for operation feedback labels; use `@app.label` for static or high-frequency mirror text.

`app.run(stages=..., tabposition=...)` and `@app.stages` provide state-driven screen switching (one visible stage at a time). Theme helpers (`apply_theme`, `tokens`, layout chrome) ship in the package root — see `examples/header_demo.py`.

Common options:
- `font`: `(family, size[, weight])` tuple, e.g. `font=("TkDefaultFont", 18, "bold")`
- `padding`: internal padding; integer or `(x, y)` / `(left, top, right, bottom)` tuple, e.g. `padding=4` or `padding=(4, 2)`

Label options: `font`, `anchor`, `justify`, `padding`, `width`.

Entry options: `placeholder`, `show`, `font`, `padding`, `width`, `state`.
- `padding` is the declarative way to increase visual height (ttk.Entry does not support `height`).

Button, checkbutton, radiobutton, spinbox, combobox, listbox, text options:
- `font` is accepted uniformly. Under the hood, ttk widgets use a derived style so the rest of the theme (colors, maps, layout) is inherited.

`@app.message` creates an auto-wrapping label. `width` sets initial pixel width; `auto_width=True` (default) tracks parent container resize.

---

## Typed Constants

```python
from nextpytk.types import Side, Fill, Sticky, State, Orient

Layout().section("msg", side=Side.LEFT, fill=Fill.X)
```

Values use `str` literals compatible with tkinter. `SideLike` / `FillLike` etc.
accept raw strings too.

| Type | Namespace | Example |
|------|-----------|---------|
| `Side` | `Side.TOP/BOTTOM/LEFT/RIGHT` | pack side |
| `Fill` | `Fill.X/Y/BOTH/NONE` | pack fill |
| `Sticky` | `Sticky.NSEW/LEFT_RIGHT/TOP/BOTTOM/LEFT/RIGHT` | grid sticky |
| `State` | `State.NORMAL/DISABLED/ACTIVE` | widget state |
| `Orient` | `Orient.HORIZONTAL/VERTICAL` | scale orientation |
| `Relief` | `Relief.FLAT/RAISED/SUNKEN/GROOVE/RIDGE/SOLID` | border style |
| `Justify` | `Justify.LEFT/RIGHT/CENTER` | text alignment |
| `SelectMode` | `SelectMode.SINGLE/BROWSE/MULTIPLE/EXTENDED` | listbox mode |
| `EventSeq` | `EventSeq.RETURN/ESCAPE/BACKSPACE/DELETE/TAB/...` | event sequences for bindings |
| `EventSeq` (mouse) | `EventSeq.BUTTON_1/2/3`, `DOUBLE_BUTTON_1/2/3`, `PRIMARY_DOUBLE_CLICK` | mouse event sequences |
| `EventSeq` (virtual) | `EventSeq.LISTBOX_SELECT/COMBOBOX_SELECTED/NOTEBOOK_TAB_CHANGED/...` | virtual events |

---

## Schema Export

`app.schema()` returns a JSON-compatible snapshot of registered widgets
(`name`, `kind`, `label`, `role`, `description`, plus kind-specific fields).

```python
@app.label("temperature")
def t():
    return "25°C"

app.schema()
# → {"title": "...", "widgets": [{"name": "temperature", "kind": "label", ...}]}
```

---

## Layout debug

After widgets are built, `app.debug_layout()` returns JSON-compatible geometry
and pack/grid info for every registered widget (useful for clipping, minsize,
and layout regressions).

```python
app.run(layout=["msg", "go"])  # or build via tests / custom runner
print(app.debug_layout())
# → {"title": "...", "sections": [{"widgets": [{"name": "msg", "geometry": ..., ...}, ...]}]}
```

---

## Async-Native (asyncio + Tkinter)

`app.run_async()` runs the app on an asyncio event loop, cooperatively scheduled
with the Tk main loop via `root.tk.dooneevent(0)`.
`app.spawn(coro)` schedules async tasks during GUI runtime.
`@app.job(name)` registers async callables.

```python
@app.job("scan")
async def scan(vals):
    result = await asyncio.to_thread(some_blocking_call)
    return {"status": "done"}

app.run_async(layout=Layout().section("status"))
```

## Examples

```bash
uv run python examples/grid_temp.py          # temperature converter
uv run python examples/task_panel.py          # multi-button panel
uv run python examples/multiscreen.py         # order app with screens
uv run python examples/widget_gallery.py      # all widget types
uv run python examples/header_demo.py         # Layout.header / .status chrome
uv run python examples/combobox_demo.py       # ttk.Combobox
uv run python examples/menubar_demo.py        # menubar
uv run python examples/disk_usage_flat_async.py       # ncdu-style viewer (async)
```

---

## Requirements

- Python 3.13+ (`requires-python`; examples default to 3.14 via `Makefile` `PYTHON=...`)
- Tkinter support in your Python build
- No other dependencies

> Note: On some macOS environments, `uv` + `3.14+freethreaded` can fail at Tk startup with `Can't find a usable init.tcl`.
> You can switch runtimes per command, e.g. `make run PYTHON=3.13`, `make run PYTHON=3.14+freethreaded`, `make run PYTHON=3.15`.

---

## Related Projects

- **`tkinter` (stdlib)**: nextpytk builds on top — adding Decorator / Schema / A11y layers.
- **`ttk`**: Native look and accessibility; nextpytk prefers ttk widgets where available.
- **`CustomTkinter`**: Modern look via Canvas rendering. nextpytk takes the opposite approach: use native widgets and embed A11y from the start.
- **`TkRouter`** (israel-dryer, author of ttkbootstrap): Declarative view routing with URL-style paths, animated transitions, and history stack. Complements nextpytk's `multiview` — routing vs widget composition.

## License

MIT

## Author

Takuya Nishimoto — Shuaruta Inc.
