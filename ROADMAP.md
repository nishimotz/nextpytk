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

## Snapshot (v0.4.1) — post-0.4 fixes

### Text widget ergonomics

- `app.text_widget(name)` returns the real `tk.Text` instance (the outer container is still available via `app.widget(name)`).
- `app.text_get(name)` returns the current full contents.
- `text` widgets now sync from state via `apply_state({name: ...})`, including read-only panes.
- `_on_text_change()` now reads from the real `tk.Text` instead of the empty container frame.
- A11y traits now attach to the real `tk.Text` rather than the container frame.

### Layout documentation

- Horizontal splits are already supported via `app.paned(..., orient=Orient.HORIZONTAL)` and `Layout.paned(...)`; see `examples/paned_split.py` and `examples/text_sync_demo.py`.
- `on_ready` is intended for post-build setup, not reparenting already-packed widgets. Use up-front `paned` / `grid` / `section` declarations for dynamic-looking layouts.
- The reported layout issue was **not** a nextpytk bug: widgets were placed in row 0 but `row_weights(0, 1)` gave all vertical stretch to the empty row 1. The framework behaved as documented; the fix was on the application side to use `row_weight(0, 1)` or a `paned` layout. This motivated stronger README warnings and the deprecation of the index-order plural methods below.

### Deprecations in v0.4.1 (removal in v0.5.0)

- `col_weights(*weights)`, `row_weights(*weights)`, `col_minsizes(*sizes)`, and `row_minsizes(*sizes)` on `_GridBuilder` are now deprecated. They assigned weights by index position, which was easy to misuse.
- `LayoutBuilder.grid(col_weights=..., row_weights=...)` keyword arguments are also deprecated.
- Migrate to the explicit singular API: `col_weight(col, weight)`, `row_weight(row, weight)`, `col_minsize(col, size)`, `row_minsize(row, size)`.

### Design system documentation (v0.4.1)

- Added a "Design System" section to README covering `Fill`/`Sticky`/`Orient` typed constants, `SPACE` token usage, and theme helpers.
- Documented the `SPACE` scale (`1:4, 2:8, 3:12, 4:16, 6:24, 8:32`) and the rule of using tokens instead of bare integers for padding/spacing.
- Updated `examples/grid_temp.py` and `examples/widget_gallery.py` to use the singular weight/min size API and `SPACE` tokens.

### Widget-level font and padding (v0.4.1)

- Added `font=` to `@app.button`, `@app.entry`, `@app.checkbutton`, `@app.radiobutton`, `@app.text`, `@app.spinbox`, `@app.listbox`, and `@app.combobox` (in addition to the existing `@app.label`).
- Added `padding=` to `@app.entry` so users can declaratively increase visual height (`ttk.Entry` does not expose `height` directly).
- For ttk widgets whose widget-level `configure()` rejects `-font` / `-padding` (Button, Entry, Checkbutton, Radiobutton), nextpytk now creates a derived `ttk.Style` per widget. The new style inherits the base style's layout and theme, applies only the requested overrides, and leaves other theme properties intact.
- Updated README.md, README.ja.md, and `tests/test_api.py` to cover the new options.

### Theme API redesign (v0.4.1)

- `TkApp(theme=...)` now accepts `bool | str`.
  - `"kizashi"` (default) applies the built-in Kizashi design system.
  - `"none"` leaves the platform default ttk theme untouched.
  - Any other string switches to that installed ttk theme without Kizashi overrides.
- `theme=True` and `theme=False` are deprecated in v0.4.1 and will be removed in v0.5.0. Migrate to `"kizashi"` and `"none"`.
- Updated `README.md`, `README.ja.md`, and `tests/test_api.py`.

### Deferred

- `listbox` callback stays index-based by design (unifies with `treeview`, handles duplicate items, and avoids forcing the framework to reverse-map strings). Passing the display string would be a breaking change and is intentionally not pursued.

---

## Near term (post-0.4.1)

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
- [x] listbox callback value design: keep selection index (unify with `treeview`)

### Layout DSL

- [x] Deprecate index-order plural methods `col_weights`/`row_weights`/`col_minsizes`/`row_minsizes` in 0.4.1 (remove in 0.5.0).
- [ ] CSS-grid-inspired layout API for 0.5.0: explicit `grid-template-columns` / `grid-template-rows` strings (e.g. `"1fr 2fr"`, `"auto 1fr"`), area-based placement, and gap tokens. Reduce misuse by making rows/columns and widget placement visually aligned in one declaration.
- [ ] Nested frames (`Layout` inside `Layout`)
- [ ] Global default for `padx`/`pady`

### Agent / LLM integration

- [ ] Expose `schema()` as Function Calling definition (bind `sequence`, treeview column defs, etc.)
- [ ] `@agent_tool` integration (GUI operations as agent vocabulary)
- [ ] `@app.filepicker` — `filedialog` wrapper (tool name in schema)

---

### v0.5.0 themes / chrome decoupling

- Remove deprecated `theme=True/False` support; `theme` becomes `str` only.
- Decouple `Layout().header()` / `.status()` chrome from Kizashi-specific tokens so they render safely with any ttk theme (`"none"`, `"clam"`, etc.).
- Extract Kizashi as a standalone ttk theme package so it can be proposed upstream or reused independently of nextpytk.

### Longer term

### ttk Style layer

- [x] Theme switching (`ttk.Style().theme_use(...)`)
- [ ] `Layout.style("my_button", background=..., font=...)` style definitions

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
