# ROADMAP — nextpytk

## Snapshot (v0.3.0)

### Implemented widgets (`@app.*`)

| kind | Notes |
|------|-------|
| `label` / `status` / `message` | Display / word-wrap |
| `button` / `entry` | ttk, `state=` support |
| `checkbutton` / `radiobutton` / `scale` / `spinbox` | ttk |
| `text` / `listbox` / `canvas` | tk (Text: tags, paired sync pending) |
| `treeview` | Multi-column (`show="headings"`) |
| `paned` | `ttk.Panedwindow` + `with app.pane(...)` |
| `progressbar` | `state[key]` / `{name}_running` for determinate/indeterminate |
| `bind` | Global shortcuts (annotates matching button) |

Infrastructure: `Layout` (pack/grid), `@app.multiview`, `run` / `run_async` / `spawn` / `@app.job`, `schema()`, builder registry, a11y choke point `_apply_a11y`.

---

## Near term (v0.3.x)

### Type hints

- [ ] TypedDict / Protocol for decorator arguments (Pyright/mypy completion)
- [ ] Literal types for tkinter constants (`tk.LEFT`, `tk.RIGHT`, `tk.NSEW`, etc.)
- [ ] Fluent API equivalent to `_GridBuilder.columnconfigure`

### Widget expansion

- [ ] `@app.combobox` / `@app.menubar`
- [ ] Per-widget `bind` (`<<ListboxSelect>>`, `<Double-1>`, etc. — separate from global `bind`)
- [ ] listbox callback value design: pass selection index instead of display string (unify with `treeview`)
- [ ] `@app.text` enhancements — `tag_config`, read-only, paired sync scroll

### A11y

- [ ] Tk 9.1 `tk accessible set_acc_*` real-device verification (9.1b0 + NVDA)
- [ ] Role vocabulary mapping to Tk side
- [ ] Automatic `emit_selection_change` (leverage `apply_state` knowing which widgets changed)

### Layout DSL

- [ ] Nested frames (`Layout` inside `Layout`)
- [ ] Global default for `padx`/`pady`
- [ ] `Layout.paired(..., sync_yscroll=True)` — left/right text sync

### Public runtime API

- [x] `build_widgets()`, `widget()`, `widget_kind()`, `widget_specs()`
- [x] `apply_state()`, `sync()` — reusable from custom runners
- [x] `app.run(multiview="...")` entry point
- [x] `register_widget_builder()` — public API for custom kinds

### Agent / LLM integration

- [ ] Expose `schema()` as Function Calling definition (bind `sequence`, treeview column defs, etc.)
- [ ] `@agent_tool` integration (GUI operations as agent vocabulary)
- [ ] `@app.filepicker` — `filedialog` wrapper (tool name in schema)

---

## Longer term

### ttk Style layer

- [ ] `Layout.style("my_button", background=..., font=...)` style definitions
- [ ] Theme switching (`ttk.Style().theme_use(...)`)

### Async job integration

- [x] `app.run_async()` + `app.spawn()` — async event loop coexisting with Tk
- [x] `app.spawn(asyncio.to_thread(...))` for non-blocking background jobs
- [x] Sync example: `disk_usage_flat_viewer.py`
- [x] Async example: `disk_usage_flat_async.py` (`app.run_async()` + `app.spawn()`)
- [x] `@app.job(name)` — register async callbacks as @app decorators

### Declarative components

- [ ] `@app.component` decorator (React-like reuse, replacing `Layout`)
- [ ] State type definitions and validation (no Pydantic)

### Testing

- [x] Headless execution tests (`tests/` — withdrawn root, build/apply_state/callback drive)
- [ ] WidgetSpec unit tests
