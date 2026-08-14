# nextpytk

Accessible, declarative Tkinter applications from ordinary Python functions.

Register widgets as plain Python functions, declare layout separately, and
keep roles/descriptions in one place. The decorator style is Flask-inspired;
`schema()` exports the registered widget structure as JSON-compatible data.
Uses ttk widgets where available.

---

## Quick Start

Start with an app where a button updates its own label.

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

That's it: a window appears with a button labeled `hello`. Press it and the
label becomes `world`.

---

## How it works

The minimal example packs a lot in. Let's unpack it.

```python
@app.button("hello")
```

Registers a button named `hello`. When `label=` is omitted, the widget name is
used as the button text.

```python
def on_hello():
    return "world"
```

The callback runs when the button is pressed. Returning a plain string updates
that button's own label — it's sugar for `{"hello": "world"}`.

```python
app.run()
```

With no `layout=`, registered widgets are arranged automatically into a single
column, so you don't have to declare one for a simple app.

The basic flow is:

* Register widgets by name
* Return a `dict` (or a plain string) from a callback
* `state` updates and matching widgets refresh

---

## Using input values

Next, change the app so you type a name and press Greet.

```python
from nextpytk import TkApp

app = TkApp(title="Hello")

app.add_entry("name", placeholder="Name")
app.add_status("msg", text="Enter your name")

@app.button("greet", label="Greet")
def on_greet(values):
    name = values["name"]
    return {"msg": f"Hello, {name}!"}

app.run(layout=["name", "greet", "msg"])
```

When you only need to read field values on button click without subscribing to live typing events, you can use direct registration methods like `app.add_entry(...)` and `app.add_status(...)` to avoid writing empty callback functions.
(To react to keystrokes in real time, decorate with `@app.entry("name") def on_name(value): ...`).

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
| `Wrap` | `Wrap.WORD/NONE/CHAR` | text wrap mode |
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

### Layout spacing

The default block padding comes from the design token `SPACE[1]` (4 px). Pass
`spacing=...` to a `Layout` constructor to change the default padding for every
block it creates:

```python
from nextpytk import tokens

layout = Layout(spacing=2).section("a").section("b").grid().cell("c").end_grid()
```

`spacing` accepts a key from `nextpytk.tokens.SPACE` (1, 2, 3, 4, 6, 8). It sets
the default `padx` and `pady` used by `section()`, `grid()`, `paned()`, grid
`cell()` placements, and nested frames. Explicit `padx`/`pady` arguments still
override the default.

For finer control, pass `padx` or `pady` directly to the constructor:

```python
Layout(padx=tokens.SPACE[4], pady=tokens.SPACE[3]).section("a")
```

### Nested frames

A `Layout` can be placed inside a named frame to group widgets visually without
mixing pack and grid in the same parent. The inner layout owns its own spacing
and may use any layout style (pack sections, grid, paned, or further nested
frames).

```python
inner = Layout().section("a", "b")
outer = Layout().section("title").frame("group", inner).section("ok")
app.run(layout=outer)
```

`frame(name, layout, side=..., fill=..., expand=..., padx=..., pady=...)` packs
the inner layout as a single block. The frame itself is registered under `name`,
so it can also be placed inside a grid cell:

```python
outer = (
    Layout()
    .grid()
    .cell("label")
    .cell("group", sticky="nsew")
    .end_grid()
    .frame("group", Layout().section("a", "b"))
)
```

### Paired layout

`Layout.paired(left, right, ...)` places two widgets side by side in a
single two-column frame.  It is a lighter alternative to `app.paned` for
diff/compare views:

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

Options:

| Argument | Default | Description |
|----------|---------|-------------|
| `weight` | `(1, 1)` | Two-column `(left, right)` grid weights |
| `fill` | `"x"` | Frame `fill` passed to `pack` |
| `expand` | `False` | Frame `expand` passed to `pack` |
| `sync_yscroll` | `False` | Wire the two widgets' y-scroll commands together |
| `line_numbers` | `False` | Add read-only line-number gutters to both sides |
| `side`, `padx`, `pady`, `anchor` | — | Standard `Layout` block placement options |

When `sync_yscroll=True` and both widgets are `@app.text` widgets, scrolling
either pane moves the other.  For text widgets the same effect can also be
achieved per-widget with `@app.text(..., sync_yscroll_with="other")`; paired
layout provides a layout-level switch that works without editing widget
declarations.

With `line_numbers=True` each side gains a read-only line-number gutter. Both
panes and both gutters share a **single vertical scrollbar**, so the gutters
stay in lock-step with the content (no drift). Logical line numbers
(`1..n`) follow the pane content; the right pane's numbers update as you edit.

> **Note:** `line_numbers=True` takes precedence over `sync_yscroll`. The
> shared-scrollbar layout it installs keeps both panes (and both gutters)
> scrolled in lock-step, so passing `sync_yscroll=False` together with
> `line_numbers=True` has no effect. If the panes must scroll independently,
> leave `line_numbers` off.

### Wrap layout

`Layout.wrap()` is a wrapping flow (Flutter `Wrap` analog): widgets are not
stretched to fill a column; each keeps the width implied by its content or
`width=` and they lay out left to right, wrapping to the next row whenever the
next widget no longer fits in the remaining frame width. Widgets in the same
row are vertically centered on their midline, so a tall `entry` aligns cleanly
with a shorter `button` or `checkbutton`. The gap inherits the layout spacing
by default (`gapx`/`gapy` override it independently).

```python
TAGS = ["python", "tkinter", "async", "uv", "type hints"]
for tag in TAGS:
    @app.button(tag, label=f"#{tag}")
    def on_tag(values, tag=tag):
        return {"msg": f"Selected: {tag}"}

app.run(layout=Layout(spacing=2).status("msg").wrap(*TAGS))
```

Wrap is ideal for tag clouds, toolbars, and filter UIs. The layout recomputes
rows automatically when the window is resized. Pass `gapx`/`gapy` to override
the spacing default, and `side`/`fill`/`expand` to control how the wrap frame
is packed.

Any wrap child wrapped in `Flex(name, flex=...)` absorbs leftover horizontal
space in its row (Flutter `Expanded` analog):

```python
from nextpytk import Flex

app.run(layout=Layout().wrap("filter", Flex("search", flex=2), "ok", gapx=2))
```

For custom positioning, `Layout.flow()` takes a `FlowDelegate` (Flutter `Flow`
analog) that computes each child's `(x, y, width, height)` from the available
`Constraints`. See `examples/wrap_demo.py` for both `Flex` and `Flow` usage.

**How it works.** `wrap` and `flow` position children with `place` (absolute
x/y) because `pack` cannot reflow onto new rows — with `pack -side left` an
overflowing child simply falls off the edge. `place` therefore implies a few
constraints:

- All children share one parent frame and are `place`-managed; they cannot
  also be `pack`/`grid`-managed on the same master (mixing geometry managers
  raises `TclError: conflicting geometry managers`).
- Widths come from `winfo_reqwidth()`; the frame uses `pack_propagate(False)`
  and its height is explicit.
- On resize the flow is recomputed so rows re-wrap to the new width.

Because `place` bypasses Tk's native Tab traversal (which follows pack/grid
insertion order), `wrap` intercepts `<Tab>`/`<Shift-Tab>` and moves focus in
the visual row-major order instead. `Entry`/`Text` children are skipped (Tab
stays for text input); focus wraps between the first and last wrap item.

> **Note:** `Layout.cluster()` was renamed to `Layout.wrap()` in 0.5.0.
> `cluster()` remains as a deprecated alias and will be removed in 0.5.0.

### Dynamic region switching (swap targets)

`Layout.target()` reserves a region whose contents change at runtime, mirroring
HTMX `hx-target` / `hx-swap`. Surrounding sections (toolbar, status) stay fixed
while only the target region swaps:

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

# Switch imperatively at runtime:
app.swap_view("main_area", "file")
```

`@app.swap` variants are mounted up-front and shown/hidden via pack, so widget
state (e.g. a treeview selection or scroll position) survives switching. Each
variant is a `Layout` or a list of widget names. See
`examples/swap_demo.py`.

### Showing and hiding widgets

To show a single widget conditionally at runtime, use `app.hide(name)` /
`app.show(name)`:

```python
if should_show:
    app.show("code")   # restore to its original grid cell / pack position
else:
    app.hide("code")   # remove without losing layout geometry
```

- `app.hide(name)` removes the widget from its section (`grid_remove` /
  `pack_forget`) and remembers it, so a later `apply_state`/`sync` does not
  repack it.
- `app.show(name)` restores it to the exact grid cell or pack options it had.
- `app.is_visible(name)` reports whether the widget is currently mapped.
- `app.set_padding(name, padx=..., pady=...)` dynamically changes layout
  padding. It is **hide-aware**: while a widget is hidden the change is
  remembered and applied when `show()` restores it, instead of calling
  `pack_configure` on a `pack_forget`'d widget (which would silently re-show
  it).
- All four are safe to call on already-hidden/visible widgets, and on widgets
  that have not been built yet.

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
    .span(2).cell("title", sticky=Sticky.W)
    .next_row()
    .cell("label", sticky=Sticky.RIGHT).cell("input", sticky=Sticky.LEFT_RIGHT)
    .next_row()
    .span(2).cell("ok")
    .end_grid()
)
```

Grid builder methods:

| Method | Description |
|--------|-------------|
| `cell(*names, *, sticky, padx, pady, colspan, rowspan)` | Place one or more widgets at cursor, advance column |
| `cell_raw(widget, *, sticky, padx, pady, colspan, rowspan)` | Place a raw `tk.Widget` instance at cursor |
| `span(n)` | Set colspan for the next `cell()` call |
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
        builder.cell("celsius", "fahrenheit", sticky="ew")
        builder.next_row().span(2).cell("note")
app.run(layout=builder.build())

# Via app.layout() shortcut
with app.layout() as b:
    b.section("title")
    with b.grid():
        b.col_weight(0, 0).col_weight(1, 1)
        b.cell("celsius", sticky="ew")
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
| `@app.filepicker(name, mode=..., label=..., title=..., filetypes=..., ...)` | ttk.Button → tkinter.filedialog | selected path(s) `str`, `list[str]`, or `None` | `dict` |
| `@app.text(name, width=..., height=..., font=..., wrap=..., h_scroll=..., scrollbar=...)` | tk.Text | full content `str` | `dict` |
| `@app.scale(name, from_=..., to=..., orient=...)` | ttk.Scale | value `str` | `dict` |
| `@app.spinbox(name, from_=..., to=..., values=..., font=...)` | ttk.Spinbox | value `str` | `dict` |
| `@app.listbox(name, items=..., items_key=..., selectmode=..., font=..., events=...)` | tk.Listbox | selected index `int` (`-1` if none) | `dict` |
| `@app.canvas(name, width=..., height=...)` | tk.Canvas | — | — |

`@app.status` sets schema / accessible `role="status"` metadata. It is **not** an ARIA live region yet (planned for a later release). Prefer it for operation feedback labels; use `@app.label` for static or high-frequency mirror text.

### File picker

`@app.filepicker` creates a button that opens a tkinter file dialog.
The selected path(s) are passed to the callback; `None` on cancel.

```python
@app.filepicker("open_file", mode="open", label="Open file",
                title="Open file", filetypes=[("Text files", "*.txt")])
def pick_open_file(path: str | None) -> dict[str, Any]:
    return {"open_path": path}
```

Modes: `"open"` (default), `"open_multiple"`, `"save"`, `"directory"`.

A filepicker can also be invoked from a menubar item by using its name
as the `command`:

```python
@app.filepicker("m_open", mode="open", title="Open file")
def m_open(path):
    return {"open_path": path}

@app.menubar("menu")
def menu_bar():
    return [{"label": "File", "items": [
        {"label": "Open...", "command": "m_open"},
    ]}]
```

`app.run(stages=..., tabposition=...)` and `@app.stages` provide state-driven screen switching (one visible stage at a time). Theme helpers (`apply_theme`, `tokens`, layout chrome) ship in the package root — see `examples/header_demo.py`.

Common options:
- `font`: `(family, size[, weight])` tuple, e.g. `font=("TkDefaultFont", 18, "bold")`
- `padding`: internal padding; integer or `(x, y)` / `(left, top, right, bottom)` tuple, e.g. `padding=4` or `padding=(4, 2)`

Label options: `font`, `anchor`, `justify`, `padding`, `width`.

Entry options: `placeholder`, `show`, `font`, `padding`, `width`, `state`.
- `padding` is the declarative way to increase visual height (ttk.Entry does not support `height`).

Button, checkbutton, radiobutton, spinbox, combobox, listbox, text options:
- `font` is accepted uniformly. Under the hood, ttk widgets use a derived style so the rest of the theme (colors, maps, layout) is inherited.

Text options (continued):
- `wrap`: `Wrap.WORD` (default) / `Wrap.NONE` / `Wrap.CHAR`. `Wrap.NONE` keeps each logical line on a single row.
- `h_scroll`: when `True`, a horizontal scrollbar is added (and wired to `xscrollcommand`) so long lines are reachable, typically used with `wrap=Wrap.NONE`.
- `scrollbar`: when `False`, the vertical scrollbar is omitted. The text widget stays built and usable (set/read via `text_set` / `text_get`) but renders as a plain surface — handy for a borderless code listing.

Every widget decorator also accepts `widget_kwargs: dict` for per-widget
design-token overrides applied after construction. Keys are widget-native
tk/ttk options (`padx`, `pady`, `bg`, `fg`, `font`, …). An invalid/unknown
key is ignored rather than aborting the build:

```python
@app.text("log", wrap="none", h_scroll=True,
          widget_kwargs={"bg": "#1e1e1e", "fg": "#dcdcdc"})
def log(value): return {}
```

Runtime access: `app.text_widget(name)` returns the real `tk.Text`;
`app.layout_frame(name)` returns the layout section frame that owns a
widget (for manual grid/pack placement or re-parenting).
`app.on_text_set(name, hook)` registers a callback to run after a text
widget's content is replaced (used by paired line-number gutters).

Enum-like options (`wrap`, `state`, `orient`, `selectmode`, `mode`) are
validated at registration time: an invalid value raises a clear `ValueError`
naming the option and the allowed values, instead of failing later with a
`TclError` when the widget is built.

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

After widgets are built, `app.layout_info()` returns JSON-compatible geometry
and pack/grid info for every registered widget (useful for clipping, minsize,
and layout regressions). It is safe to call after `run()` has returned: once
the window is closed the Tk interpreter is torn down, and `layout_info()`
reports `"alive": False` with empty `sections`/`conflicts` instead of crashing
on destroyed widgets.

```python
app.run(layout=["msg", "go"])  # or build via tests / custom runner
print(app.layout_info())
# → {"title": "...", "alive": True, "sections": [{"widgets": [{"name": "msg", "geometry": ..., ...}, ...]}]}
```

> **Note:** `app.debug_layout()` is a deprecated alias for `layout_info()`
> (removed in 0.5.x). Prefer `layout_info()`.

**Detecting geometry-manager conflicts.** Mixing `pack`/`grid`/`place` on one
master (e.g. manually `pack`/`grid`-ing into a `place`-managed `wrap`/`flow`
frame) cannot be fully prevented by the DSL, so `app.check_layout_conflicts()`
inspects the widget tree and reports any such mix without waiting for a
`TclError: conflicting geometry managers`:

```python
print(app.check_layout_conflicts())
# → [{"master_class": "Frame", "managers": ["pack", "place"], ...}] on conflict
#    (a warning is also emitted for each conflict)
```

**Visual overlays.** Two helpers render debug info directly in the window, so
you can see geometry and padding where the widget actually sits (they are
`place`-managed labels over the root, so they never disturb the layout):

- `app.show_debug_padding(True)` — color-coded badges for each layer of
  whitespace: the page margin (`page`), section frames (`section`), a widget's
  own outer padding (`widget`), and its inner padding (`inner`). Badges
  re-place on resize and follow `show()`/`hide()` automatically.
- `app.show_debug_layout(True)` — each widget's `layout_info()` data (class,
  geometry, requested size, pack/grid details) at its own location.

Turn either off with `show_debug_padding(False)` / `show_debug_layout(False)`,
or pass `debug_padding=True` to `TkApp` to enable the padding overlay at
startup. Click a badge to lift it to the front.

The padding overlay is also enabled automatically at startup when the
`NEXTPYTK_DEBUG_PADDING` environment variable is set to a non-empty value other
than `0` (e.g. `NEXTPYTK_DEBUG_PADDING=1 uv run python app.py`), so you can
inspect any app's layout without editing its source.

**Page margin & widget unregister.**

- `Layout(page_margin=...)` overrides the outer `content_frame` page pad
  (default `SPACE[6]` / 24px); `app.set_page_margin(margin)` re-scales it at
  runtime (e.g. proportionally to window height).
- `app.unregister(name)` removes a registered widget spec by name (useful in
  interactive sessions); re-registering a name replaces the previous spec in
  place instead of raising `ValueError`.
- `app.hide_section(name)` / `app.show_section(name)` hide or restore an
  entire section frame (including the empty space it reserved) at runtime.
  `Layout.section(name=...)` lets you give a section a stable label;
  otherwise it is auto-derived from the first widget as
  `"<first widget>_section"` (e.g. `diagram_section`).

**For AI coding agents (headless / non-vision).** These debug facilities are
deliberately machine-readable so they work without a visible window:

- `app.layout_info()` returns **JSON-compatible data**, so an agent can read
  geometry, requested sizes, and pack/grid details as text.
- Widgets can be built headlessly — `tk.Tk(); root.withdraw()` + the `build`
  fixture pattern in `tests/conftest.py` — and inspected via `winfo_*` /
  `pack_info()`, then pinned with `assert` in unit tests.
- The overlay badges expose the same data as text: `badge.cget("text")` and
  `badge.place_info()` give the padding label and coordinates. So a badge that
  a human sees visually, an agent can assert on. "What a human sees is also
  visible to an agent."

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

---

## Escape Hatches (Interoperating with Raw Tkinter)

nextpytk is declarative, but it does not restrict raw Tkinter flexibility. When you need low-level Tk operations or custom drawing, the following escape hatches are available:

1. **Accessing underlying widget instances**:
   `app.widget(name)` / `app.get_widget(name)` returns the built `tk.Widget` / `ttk.Widget` instance.
   ```python
   raw_entry = app.get_widget("my_entry")
   raw_entry.icursor(0)
   ```

2. **Embedding raw Tkinter widgets into layouts**:
   `Layout().grid().cell_raw(widget)` allows embedding hand-built Tkinter frames or third-party controls directly into nextpytk's Grid layout.
   ```python
   custom_frame = ttk.Frame(app.root)
   Layout().grid().cell("lbl").cell_raw(custom_frame).end_grid()
   ```

3. **Direct root window control**:
   The `app.root` property gives full access to the `tk.Tk` root window for window protocols (`protocol("WM_DELETE_WINDOW", ...)`), geometry control, and window attributes.

4. **Direct access to the underlying Tcl interpreter**:
   `app.eval(script)` / `app.call(*args)` / `app.tcl` allow directly sending scripts and commands to the embedded Tcl interpreter underneath Tkinter. This provides the ultimate escape hatch for Tcl macros, high-performance scripting, or loading external Tcl/Tk packages.
   ```python
   # Direct Tcl command execution
   app.eval('puts "hello from Tcl"')
   app.call('wm', 'attributes', '.', '-topmost', '1')
   ```

---

## When to use nextpytk

### Sweet spots for nextpytk
* **Forms, Settings & Internal Dashboards**: State management (`state`) and `values` deliver predictable, one-way data flow, validation, and async background tasks without GUI freezes.
* **Accessibility-First Desktop Apps**: Built-in screen reader support (Tk 9.1 `set_acc_*`), keyboard focus navigation (Tab order), and ARIA live regions with zero boilerplate.
* **LLM & AI Agent Tooling**: `app.schema()` exports the complete UI structure as machine-readable JSON schemas (Function Calling tool definitions) for automated testing and agent interaction.
* **Async-Native Tools**: Seamless `asyncio` integration via `app.run_async()` and `@app.job` prevents threading headaches.

### When raw Tkinter or other approaches are better suited
* **Canvas-Heavy Drawing & Painting Tools**: High-frequency mouse drag events and coordinate-based item manipulation are inherently imperative and best written with raw `tk.Canvas`.
* **Real-time Games & High-framerate Animations**: Dedicated graphics frameworks or game engines are better suited.
* **Highly Dynamic Node Graph Editors**: UIs where widget trees are created and destroyed every few milliseconds benefit more from imperative lifecycle management.

---

## Examples

```bash
uv run python examples/grid_temp.py          # temperature converter
uv run python examples/task_panel.py          # multi-button panel
uv run python examples/multiscreen.py         # order app with screens
uv run python examples/widget_gallery.py      # all widget types
uv run python examples/header_demo.py         # Layout.header / .status chrome
uv run python examples/combobox_demo.py       # ttk.Combobox
uv run python examples/menubar_demo.py        # menubar
uv run python examples/filepicker_demo.py     # file picker
uv run python examples/disk_usage_flat_async.py       # ncdu-style viewer (async)
uv run python examples/paired_demo.py           # side-by-side paired layout with y-scroll sync
uv run python examples/swap_demo.py             # dynamic region switching (Layout.target + @app.swap)
uv run python examples/bottom_bar_demo.py       # pinned bottom bar (section side="bottom")
uv run python examples/live_validation.py       # live validation via Tcl-var trace ingest (ingest_trace=True)
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

## Changelog

See [CHANGES.md](./CHANGES.md) for the full release history.

## License

MIT

## Author

Takuya Nishimoto — Shuaruta Inc.
