# nextpytk — Flask-style Decorator API for Tkinter

nextpytk wraps Tkinter in Python decorators, inspired by Flask.
Widget registration and layout are decoupled via dependency injection.
All widgets expose a JSON schema for AI/LLM consumption.
Uses ttk widgets where available (Button, Entry, Checkbutton, Radiobutton, Scale, Spinbox, Notebook).

---

## Quick Start

```python
from nextpytk import TkApp, Layout

app = TkApp(title="Hello")

@app.status("msg")
def msg():
    return "Hello, world!"

@app.button("greet", label="Greet")
def on_greet(values):
    return {"msg": "Button clicked!"}

app.run(layout=Layout().section("msg").section("greet"))
```

**Three layout styles — pick the one that fits:**

```python
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

View layouts also accept lists or with-block builders:

```python
@app.multiview("main", views=["Home", "Settings"],
    view_layouts={"Home": ["title", "start"], "Settings": ["timer", "status"]})
```

---

## Layout DSL

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

Layout().grid()
  .span(2).widget("title", sticky=Sticky.W)
  .next_row()
  .widget("label", sticky=Sticky.RIGHT).widget("input", sticky=Sticky.LEFT_RIGHT)
  .next_row()
  .span(2).widget("ok")
.end_grid()
```

Grid builder methods:

| Method | Description |
|--------|-------------|
| `widget(name, *, sticky, padx, pady, colspan, rowspan)` | Place widget at cursor, advance column |
| `span(n)` | Set colspan for the next `widget()` call |
| `next_row()` | Move to next row, reset column |
| `next_col(n)` | Skip n columns |
| `at(row, col)` | Jump to absolute position |
| `col_weights(*w)` | Bulk column weights: `col_weights(0, 1, 1)` |
| `row_weights(*w)` | Bulk row weights |
| `col_weight(col, w)` | Single column weight |
| `row_weight(row, w)` | Single row weight |
| `col_minsize(col, px)` | Column minimum width |
| `row_minsize(row, px)` | Row minimum height |
| `end_grid()` | Return to Layout chain |

`col_weights(0, 1, 1)` means column 0 → weight 0, column 1 → weight 1, column 2 → weight 1.

### With-block (context manager)

```python
from nextpytk import LayoutBuilder

# Standalone builder
builder = LayoutBuilder()
with builder:
    builder.section("title")
    with builder.grid(col_weights=(0, 1)):
        builder.widget("celsius", sticky="ew")
        builder.widget("fahrenheit", sticky="ew")
        builder.next_row().span(2).widget("note")
app.run(layout=builder.build())

# Via app.layout() shortcut
with app.layout() as b:
    b.section("title")
    with b.grid(col_weights=(0, 1)):
        b.widget("celsius", sticky="ew")
app.run(layout=b.build())
```

`with b.grid(...)` auto-closes — no `end_grid()` needed.

`grid()` options available directly: `col_weights=(0,1)`, `row_weights=(...)`, `padx`, `pady`, `fill`, `expand`, `uniform`.

---

## Widget Reference

| Decorator | Widget | Callback receives | Returns |
|-----------|--------|-------------------|---------|
| `@app.label(name, font=..., anchor=..., justify=..., padding=...)` | tk.Label | — | `str` or `dict` |
| `@app.status(name)` | tk.Label (role=status) | — | `str` or `dict` |
| `@app.message(name, width=..., auto_width=...)` | tk.Label (auto-wrap) | — | `str` or `dict` |
| `@app.button(name, label=..., enabled_if=...)` | ttk.Button | entry values `dict` | `dict` |
| `@app.job(name)` | async callable | entry values `dict` | `dict` |
| `@app.entry(name, placeholder=..., show=...)` | ttk.Entry | `str` | `dict` |
| `@app.checkbutton(name, text=...)` | ttk.Checkbutton | `bool` | `dict` |
| `@app.radiobutton(name, text=..., value=..., group=...)` | ttk.Radiobutton | selected value `str` | `dict` |
| `@app.text(name, width=..., height=...)` | tk.Text | full content `str` | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | value `str` | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=...)` | ttk.Spinbox | value `str` | `dict` |
| `@app.listbox(name, items=..., selectmode=...)` | tk.Listbox | selected item `str` | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | — | — |

Label options:
- `font`: e.g. `font=("TkDefaultFont", 18, "bold")`
- `anchor`: e.g. `anchor="e"` (right-aligned)
- `justify`: multi-line alignment, e.g. `justify="right"`
- `padding`: e.g. `padding=4` or `padding=(4, 2)`

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

---

## Schema Export (Agent/LLM)

```python
@label("temperature")
def t(): return "25°C"

app.schema()
# → {"title": "...", "widgets": [{"name": "temperature", "kind": "label", ...}]}
```

Output is JSON-compatible and can serve as LLM Function Calling definitions.

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
uv run python examples/disk_usage_flat_viewer.py      # ncdu-style viewer (sync)
uv run python examples/disk_usage_flat_async.py       # ncdu-style viewer (async)
```

---

## Requirements

- Python 3.14 by default (`PYTHON=...` override supported)
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
