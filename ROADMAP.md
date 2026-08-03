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

## Snapshot (v0.4.2) — event-sequence generalization + listbox items_key

### Problem

`@app.bind(...)` accepts arbitrary Tk event strings, but the only typed constants lived under `nextpytk.types.ListboxEvent` (e.g. `ListboxEvent.RETURN`). Using a listbox-oriented name for a global shortcut or an entry-level Enter binding was confusing.

### Change

- Added a generic `nextpytk.types.EventSeq` class with common event sequences: `RETURN`, `ESCAPE`, `BACKSPACE`, `DELETE`, `TAB`, `DOUBLE_BUTTON_1`, `DOUBLE_BUTTON_2`, `DOUBLE_BUTTON_3`, `LISTBOX_SELECT`.
- Kept `ListboxEvent` as a backward-compatible subclass of `EventSeq` so existing code continues to work. Existing constants (`SELECT`, `RETURN`, `KEY_BACKSPACE`, `KEY_DELETE`) still resolve to the same string values. `DOUBLE_CLICK` is kept as a deprecated alias of `DOUBLE_BUTTON_1` and will be removed in v0.5.0.
- Updated `EventSeqLike` / `ListboxEventLike` to share the same literal union.
- Updated `app.py` docstrings for `@app.bind` and `@app.listbox` to reference `EventSeq` instead of `ListboxEvent`.

### listbox / combobox dynamic choices

- Added `items_key=` option to `@app.listbox` for state-driven list contents, symmetric to `treeview`'s existing `rows_key=`.
- Added `values_key=` option to `@app.combobox` for state-driven dropdown values, following the same widget-native naming principle.
- With these keys, `apply_state({items_key: [...]})` / `apply_state({values_key: [...]})` refresh the widget choices while keeping the selection in `state[name]` / `state[key]`.
- Static `items=` / `values=` remain available and still work as before. When both are provided, the dynamic key takes precedence at runtime.
- Full (`apply_state`) and partial (`_apply_state_dict`) updates both refresh the affected widgets when the dynamic key is touched.
- Selection is kept when it remains valid; if it becomes invalid (removed from values, out of range for listbox) it is reset to the widget's empty state.

### entry widget-level events

- Added `events=` option to `@app.entry` for widget-level event bindings.
- Accepts `dict[str, ListboxEventHandler]` mapping event sequences (e.g. `EventSeq.RETURN`) to handlers.
- Handlers receive a dict of current effective entry values (same shape as button callbacks) and may return a state update dict.
- Enables patterns like "press Enter in the search entry to trigger search" without a global `<Return>` bind or an application-level button.

### A11y-aware primary mouse-button helpers

- Added `EventSeq.PRIMARY_CLICK`, `EventSeq.PRIMARY_DOUBLE_CLICK`, and `EventSeq.PRIMARY_BUTTON_RELEASE` lazy descriptors to `nextpytk.types`. These return the tkinter event sequence for the OS-configured primary mouse button, accounting for left/right button swap on Windows, macOS, and Linux/GNOME. (The underlying `primary_click()`, `primary_double_click()`, and `primary_button_release()` functions are also available for direct use.)
- `_primary_button_number()` detects the swap setting per platform and caches the result with `functools.lru_cache(maxsize=1)` so repeated event lookups do not hit the OS each time.
- `EventSeq.PRIMARY_CLICK`, `EventSeq.PRIMARY_DOUBLE_CLICK`, and `EventSeq.PRIMARY_BUTTON_RELEASE` are lazy descriptors that re-evaluate on each access (the underlying `_primary_button_number()` is cached, so the cost is negligible). These are the recommended way to reference primary-button events in widget-level bindings (e.g. `events={EventSeq.PRIMARY_DOUBLE_CLICK: ...}` on `@app.listbox`).
- Updated `examples/disk_usage_flat_async.py` and the `@app.listbox` docstring to use `EventSeq.PRIMARY_DOUBLE_CLICK` instead of the deprecated `EventSeq.DOUBLE_CLICK`.

### Tests

- Added `tests/test_types.py` covering `DOUBLE_BUTTON_*`, the `DOUBLE_CLICK` alias, default primary-button behavior, and mocked Windows/macOS/GNOME left-handed settings returning the swapped button number.

### Design principle

- Use the tkinter-native vocabulary per widget: listbox has "items", treeview has "rows", combobox has "values". The corresponding dynamic keys are `items_key`, `rows_key`, and `values_key`. This is more intuitive than forcing a single generic name across widgets.

### Deprecation note

- `ListboxEvent` is soft-deprecated in v0.4.2. New code should use `EventSeq` directly. No removal timeline yet.

---

## Snapshot (v0.4.3) — filepicker + layout blocks

- Added `@app.filepicker` (`filedialog` wrapper; `mode=` open/save/directory/open_multiple).
- Added `Layout(spacing=...)` for a layout-wide SPACE token default (padx/pady inheritance).
- Added `Layout.frame(...)` for nested layouts (`Layout` inside `Layout`).
- Added `Layout.cluster(...)` wrapping flow: widgets keep content/`width=` sizes and wrap left-to-right.
- Added `Layout.paired(left, right, ..., sync_yscroll=)` for side-by-side panes with optional text y-scroll sync.
- Docs/examples/tests for the above (`filepicker_demo`, `nested_frame_demo`, `cluster_demo`, `paired_demo`).

---

## Snapshot (v0.4.4) — text wrap/h-scroll, public runtime API

### Text widget ergonomics (continued)

- Added `wrap=` option to `@app.text` for logical-line display control:
  - `Wrap.WORD` (default) — wrap at word boundaries.
  - `Wrap.NONE` — keep each logical line on one row (requires horizontal scrolling).
  - `Wrap.CHAR` — wrap at any character boundary.
- Added a new `nextpytk.types.Wrap` typed-constant class and `WrapLike` union.
- Added `h_scroll=` option to `@app.text`: when True, a horizontal scrollbar is added (and wired to `xscrollcommand`) so long lines are reachable in `Wrap.NONE` mode. The horizontal scrollbar is tracked in `app._text_hscrollbars`.

### Decorator type-definition sync

- `TreeviewOptions.double_click` is now typed and honored by `@app.treeview`.
  - Defaults to `True`: the `activate` handler fires on double-click (previous behavior).
  - When `False`, `activate` fires on a single `ButtonRelease-1` instead.
- `_on_treeview_activate` accepts an optional `event` argument so the single-click binding can reuse it.

### Public runtime API

- Added `app.layout_frame(name)` — returns the layout frame that owns a widget (the section frame), so applications can place/re-parent widgets with grid/pack without reaching into the private `_widget_masters`.
- This is the public replacement for the internal `_widget_masters` access that previously forced applications to depend on private state.

### Per-widget design-token overrides

- All widget decorators now accept `widget_kwargs: dict[str, Any]` (on `CommonWidgetOptions`).
- Keys are widget-native tk/ttk options (`padx`, `pady`, `bg`, `fg`, `font`, …); values are the native values.
- Overrides are applied after construction by `_apply_widget_overrides()`. An invalid/unknown key raises no error: a `TclError` is swallowed so one bad key does not abort the build.
- This removes the need to monkey-patch the shared `tokens` module to tweak a single widget's appearance.

### Decorator argument validation

- Added `_validate_choice()` / `_validate_positive_int()` helpers used by the decorators to reject invalid enum-like and non-positive-int options at **registration time** (before any Tk widget is built).
- Validated options:
  - `text`: `state` (`normal`/`disabled`/`active`), `wrap` (`word`/`none`/`char`)
  - `scale`, `progressbar`, `paned`: `orient` (`horizontal`/`vertical`)
  - `listbox`, `treeview`: `selectmode` (`single`/`browse`/`multiple`/`extended`)
  - `filepicker`: `mode` (`open`/`open_multiple`/`save`/`directory`)
  - `progressbar`: `mode` (`determinate`/`indeterminate`)
- A mistyped value (e.g. `wrap="wrap"`) now raises a clear `ValueError` naming the option, widget, and allowed values — instead of a cryptic `_tkinter.TclError` at runtime.

### Paired line-number gutters

- Added `line_numbers=True` to `Layout.paired(...)`.
- Each side gains a read-only line-number gutter (`disabled` tk.Text, `takefocus=0`, arrow cursor).
- **Reliable sync via a single shared vertical scrollbar**: both panes and both gutters drive one shared scrollbar. Each widget's `yscrollcommand` is chained so scrolling any widget moves the other three, and the shared scrollbar's `command` drives all four. This avoids the `yview_moveto` drift that plagued per-widget gutter chaining.
- Gutters stay in sync when content changes via `app.text_set()` (a new `app.on_text_set()` hook) and when the editable right pane is typed into (`<KeyRelease>`).
- Added `examples/paired_demo.py` demonstrating `line_numbers=True`.
- The new `app.on_text_set(name, hook)` public helper lets layout features react to programmatic text replacement.

### Dynamic layout switching (swap targets)

- Added `Layout.target(name)` to reserve a swap region whose contents change at runtime (mirrors HTMX `hx-target`).
- Added `@app.swap(name, variants=..., default=...)` to declare the layouts that can fill a target (mirrors HTMX `hx-swap`), and `app.swap_view(name, variant)` to switch imperatively.
- Variants are mounted up-front and shown/hidden via `pack`/`pack_forget`, so widget state (treeview selection, scroll position) survives switching. Surrounding `Layout.section` blocks (toolbar, status) stay fixed.
- Added `examples/swap_demo.py` (folder view <-> paired diff view).

### Tests

- Added `tests/test_widget_public_api.py` covering `layout_frame` and `widget_kwargs` (applied, ignored-invalid).
- Added `tests/test_decorator_validation.py` covering invalid-option rejection for every validated widget.
- Added wrap/h-scroll tests to `tests/test_text.py`.
- Added `double_click` tests to `tests/test_state.py`.
- Added paired line-number gutter tests to `tests/test_paired.py` (creation, population, shared-scrollbar sync).
- Added swap tests to `tests/test_swap.py` (variant registration, build, switching, back-and-forth, pre-build intent).
- Suite grew from 181 to 208 passing; pyright clean.

---

## Snapshot (v0.4.5) — Flutter-style layout vocabulary

### `cluster` → `wrap` rename

- `Layout.cluster()` renamed to `Layout.wrap()`, matching Flutter's `Wrap`
  widget. `cluster()` is kept as a deprecated alias (emits a
  `DeprecationWarning`) and will be removed in v0.5.0.
- `LayoutBuilder.cluster()` → `LayoutBuilder.wrap()` (same alias story).
- `examples/cluster_demo.py` → `examples/wrap_demo.py`; `tests/test_cluster.py`
  → `tests/test_wrap.py`.
- `gap` keyword deprecated in favor of explicit `gapx`/`gapy` (SPACE tokens).

### `Flex` — absorb leftover space (Flutter `Expanded` analog)

- Added `nextpytk.types.Flex(name, flex=...)`; a `wrap` child wrapped in `Flex`
  absorbs a share of its row's leftover horizontal space proportional to its
  flex factor, instead of keeping natural content width.
- `widget_names()` and `mount_frames_into` resolve `Flex`-wrapped names.

### `FlowDelegate` / `Layout.flow` — custom flow (Flutter `Flow` analog)

- Added `nextpytk.layout.Constraints` (width/height/min/max) and
  `nextpytk.layout.FlowDelegate` (abstract `compute_positions` /
  `compute_height`).
- `Layout.flow(*widgets, delegate=...)` and `LayoutBuilder.flow(...)` position
  children via the delegate using `place`; recomputed on `<Configure>` resize.
- `_place_flow` / `_Flow` block dispatched in `mount_frames_into` /
  `pack_children_for`.
- `examples/wrap_demo.py` demonstrates `wrap`, `wrap`+`Flex`, and a
  `GridDelegate` flow.

### Theme / debug

- Button styles use `width=0` (cancel clam's `width=-11` min ~182px) so button
  width tracks label text.
- `_check_radio_padding` unified to (16,12) to match buttons;
  `indicatormargin=(0,0,SPACE[2],0)` adds 8px between indicator and label
  (clam ignores `indicatorpadding`).
- `debug_layout()` detects geometry-manager conflicts;
  `check_layout_conflicts()` warns on each.

---

## Snapshot (v0.4.6) — section placement fix + layout ergonomics

### Bug fix: `section(..., side=...)` now controls the section frame placement

- `_pack_section_frame` hardcoded `side="top"`, ignoring the requested
  placement side. A `side="bottom"` section declared after an `expand=True`
  block (e.g. a status bar under a growing body) was pushed off-view and
  collapsed to 1x1.
- Fixed by honoring `block.side` on the section frame pack call.

### Child packing decoupled from frame placement

- Added `_Row.child_side` to separate the section frame's placement side
  (`side`) from the side used to pack children *inside* the frame. A
  multi-widget section still lays its children out left-to-right (`"left"`)
  regardless of where the frame itself is placed (`side="top"`/`"bottom"`/
  `"left"`/`"right"`); a single-widget section packs its child with the
  frame's own placement side.

### Tests / example

- Added `tests/test_layout_side.py` (regression coverage: frame side
  honored, default `top` preserved, multi-widget child `"left"` + frame
  `"top"`/`"bottom"`).
- Added `examples/bottom_bar_demo.py` demonstrating a `side="bottom"` bar
  pinned below an expandable body.

---

## Near term (post-0.4.5)

### A11y

- [ ] `@app.status` live-region behavior (ARIA `aria-live` equivalent / WCAG 4.1.3)
- [ ] Tk 9.1 `tk accessible set_acc_*` real-device verification (9.1b0 + NVDA)
- [ ] Role vocabulary mapping to Tk side
- [ ] Automatic `emit_selection_change` (leverage `apply_state` knowing which widgets changed)

### Type hints

- [ ] Further TypedDict / Protocol coverage for decorator arguments
- [ ] Fluent API equivalent to `_GridBuilder.columnconfigure`

### Widget expansion

- [x] Per-widget `bind` for entry and listbox (`events=` on `@app.entry` and `@app.listbox`)
- [x] Per-widget `bind` for other widgets via `widget_kwargs` / widget-level options
- [ ] Per-widget `bind` for other widgets (`text`, `combobox`, `treeview`, `button`, etc.)
- [x] listbox callback value design: keep selection index (unify with `treeview`)
- [x] `@app.filepicker` — `filedialog` wrapper (schema/tool naming still open)
- [x] Text `wrap=` / `h_scroll=` options (v0.4.4)

### Layout DSL

- [x] Deprecate index-order plural methods `col_weights`/`row_weights`/`col_minsizes`/`row_minsizes` in 0.4.1 (remove in 0.5.0).
- [ ] CSS-grid-inspired layout API for 0.5.0: explicit `grid-template-columns` / `grid-template-rows` strings (e.g. `"1fr 2fr"`, `"auto 1fr"`), area-based placement, and gap tokens. Reduce misuse by making rows/columns and widget placement visually aligned in one declaration.
- [x] Nested frames (`Layout` inside `Layout`) via `Layout.frame(...)`
- [x] Global default for `padx`/`pady` via `Layout(spacing=...)`
- [x] `Layout.cluster(...)` wrapping flow; `Layout.paired(..., sync_yscroll=)`
- [x] `Layout.cluster(...)` → `Layout.wrap(...)` rename with deprecated alias (v0.4.5)
- [x] `Flex` (Flutter `Expanded` analog) for `wrap` (v0.4.5)
- [x] `FlowDelegate` / `Layout.flow` custom flow (Flutter `Flow` analog) (v0.4.5)
- [x] `Layout.paired(..., line_numbers=True)` read-only line-number gutters (v0.4.4)
- [x] `Layout.target(...)` + `@app.swap(...)` dynamic region switching (v0.4.4)

### Agent / LLM integration

- [ ] Expose `schema()` as Function Calling definition (bind `sequence`, treeview column defs, etc.)
- [ ] `@agent_tool` integration (GUI operations as agent vocabulary)
- [ ] Surface `@app.filepicker` in `schema()` / tool vocabulary

---

### v0.5.0 themes / chrome decoupling

- Remove deprecated `theme=True/False` support; `theme` becomes `str` only.
- Remove deprecated `EventSeq.DOUBLE_CLICK`; use `EventSeq.PRIMARY_DOUBLE_CLICK` or `DOUBLE_BUTTON_1`.
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
