# ROADMAP — nextpytk

## Snapshot (v0.4.0)

### Implemented widgets (`@app.*`)

| kind | Notes |
|------|-------|
| `label` / `status` / `message` | Display / word-wrap. `status` sets `role=status` metadata (not a live region yet) |
| `button` / `entry` | ttk, `state=` support |
| `checkbutton` / `radiobutton` / `scale` / `spinbox` | ttk |
| `combobox` | ttk.Combobox (`readonly`, `values`) |
| `menubar` | Window menubar with cascades / `enabled_if` |
| `text` / `listbox` / `canvas` | tk (Text: tags, readonly, paired y-scroll sync) |
| `treeview` | Multi-column (`show="headings"`) |
| `paned` | `ttk.Panedwindow` + `with app.pane(...)` |
| `progressbar` | `state[key]` / `{name}_running` for determinate/indeterminate |
| `bind` | Global shortcuts (annotates matching button) |

Infrastructure: `Layout` (pack/grid, `.header()` / `.status()` chrome), `@app.multiview`, `@app.stages` / `run(stages=..., tabposition=...)`, `run` / `run_async` / `spawn` / `@app.job`, `schema()`, `debug_layout()`, builder registry, a11y choke point `_apply_a11y`.

Theme: `tokens` + `apply_theme` / layout helpers (contrast + 44px target-size regressions).

PyPI: Trusted Publishing on `v*` tag push (`.github/workflows/publish.yml`).

### Examples

- `disk_usage_flat_async.py` — async ncdu-style viewer (`run_async` + `spawn`)
- `combobox_demo.py`, `menubar_demo.py`, `header_demo.py`, `text_sync_demo.py`

---

## Near term (post-0.4)

### A11y

- [ ] `@app.status` live-region behavior (ARIA `aria-live` equivalent / WCAG 4.1.3)
- [ ] Tk 9.1 `tk accessible set_acc_*` real-device verification (9.1b0 + NVDA)
- [ ] Role vocabulary mapping to Tk side
- [ ] Automatic `emit_selection_change` (leverage `apply_state` knowing which widgets changed)

### Type hints

- [ ] Further TypedDict / Protocol coverage for decorator arguments
- [ ] Fluent API equivalent to `_GridBuilder.columnconfigure`

### Widget expansion

- [ ] Per-widget `bind` (`<<ListboxSelect>>`, `<Double-1>`, etc. — separate from global `bind`)
- [ ] listbox callback value design: pass selection index instead of display string (unify with `treeview`)

### Layout DSL

- [ ] Nested frames (`Layout` inside `Layout`)
- [ ] Global default for `padx`/`pady`

### Agent / LLM integration

- [ ] Expose `schema()` as Function Calling definition (bind `sequence`, treeview column defs, etc.)
- [ ] `@agent_tool` integration (GUI operations as agent vocabulary)
- [ ] `@app.filepicker` — `filedialog` wrapper (tool name in schema)

---

## Longer term

### ttk Style layer

- [ ] `Layout.style("my_button", background=..., font=...)` style definitions
- [ ] Theme switching (`ttk.Style().theme_use(...)`)

### Declarative components

- [ ] `@app.component` decorator (React-like reuse, replacing `Layout`)
- [ ] State type definitions and validation (no Pydantic)

### Testing

- [x] Headless execution tests (`tests/` — withdrawn root, build/apply_state/callback drive)
- [ ] WidgetSpec unit tests

---

## Earlier snapshots

### v0.3.0

Builder registry, headless tests, a11y wiring (`_apply_a11y`), error policy, bugfixes.
`run_async` / `spawn` / `@app.job`, public runtime API (`build_widgets`, `apply_state`, `register_widget_builder`, …).
