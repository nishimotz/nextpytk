# Changelog

All notable changes to nextpytk are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.9] — 2026-08-06

### Added

- Button labels can be refreshed from state. Returning a state dict whose key
  matches a button name (e.g. `{"hello": "world"}`) now updates that button's
  text in both `_sync_widgets` and `_sync_widgets_for_keys`, matching how
  `label`/`status`/`message` widgets already work. The declared `label=` text
  is preserved unless a state value is explicitly set.
- Button callback sugar: returning a plain string from a button callback
  updates that button's own label — `return "world"` is sugar for
  `return {"<button>": "world"}`.
- Automatic layout: calling `run()` / `run_async()` without `layout=` now
  arranges every registered widget into a single column in registration order
  (via the new `_auto_layout()`). Chrome helpers that already mounted
  themselves are skipped.
- Button callbacks that return a `set`/`list`/`tuple` are now rejected with a
  clear stderr warning instead of being silently ignored. `None` still means
  "no update". Warnings are centralized in `_warn_invalid_callback_return()`
  and also applied to `entry` callbacks (e.g. a stray string return).
- Layout validation: `run()` / `run_async()` warn via
  `_warn_orphan_layout_names()` when a `layout=` references a widget name that
  is not registered (previously rendered an empty section silently).

### Changed

- README Quick Start is now a minimal single-button example (label update via
  plain-string return, `app.run()` with auto layout).

### Tests

- `tests/test_api.py`: `test_button_label_updates_from_state_dict`,
  `test_button_label_updates_from_plain_string`,
  `test_auto_layout_builds_single_column`, `test_auto_layout_none_when_no_widgets`,
  `test_layout_names_detects_orphan`, `test_layout_names_collects_grid_cells`,
  `test_entry_callback_returning_string_warns`,
  `test_button_callback_returning_none_is_ignored`,
  `test_button_callback_returning_set_is_ignored_with_warning`,
  `test_button_callback_returning_list_is_ignored`,
  `test_button_callback_returning_tuple_is_ignored`.

## [0.4.10] — 2026-08-06

Bug-fix-only release (no new features or breaking changes).

### Fixed

- `debug_layout()` no longer crashes with
  `TclError: can't invoke "winfo" command: application has been destroyed`
  when called after `run()`/`mainloop` exits (the window was closed and the
  Tk interpreter torn down). It now reports `"alive": False` and returns empty
  `sections`/`conflicts` instead of raising. Each widget/master query is also
  guarded with `winfo_exists()` so a partially-torn-down tree is handled
  gracefully.
- `check_layout_conflicts()` is likewise safe to call after the app is
  destroyed (it returns an empty list instead of raising); documented on the
  method docstring.
- `FilepickerCallback` type alias consolidated to a single source in
  `types.py`. It previously existed in both `types.py` (loose `*args` form)
  and `app.py` (concrete `(str | list[str] | None) -> dict` form), where the
  `app.py` shadow hid the exported one. The concrete signature now lives in
  `types.py` only, and the shadowing redefinition in `app.py` was removed.

### Tests

- `tests/test_debug_layout.py`:
  `test_debug_layout_after_root_destroyed` (debug_layout safe after the root /
  interpreter is destroyed; also asserts `check_layout_conflicts()` is safe).
- `tests/test_types.py`: `TestFilepickerCallbackType::test_exports_concrete_signature`
  (FilepickerCallback exports the concrete single-arg signature).

## [0.4.8] — 2026-08-05

### Added

- `TkApp(..., ingest_trace=True)` — Tcl-var trace ingest. Every registered
  Tcl `Variable` gets a `trace_add("write", ...)` (installed via the new
  `_register_var` helper) that feeds `var.get()` back into Python `state`,
  so `state` is never stale even before a button callback runs. Trace events
  are queued into `_pending_ingest` and coalesced into a single sync pass at
  the next idle opportunity (`after_idle`), so per-keystroke cost stays
  constant as widget count grows. Loop guards skip writes originating from
  `apply_state`'s own `var.set` and writes during widget build.
- `examples/live_validation.py` — demonstrates per-keystroke `enabled_if` and
  live labels on an entry with no on-change logic (requires `ingest_trace=True`).

### Changed

- **Kizashi design-system polish.**
  - `window_header()` title/subtitle labels share the page ground (`BG`)
    background and use `SPACE[2]` internal padding; a `SPACE[4]` spacer
    separates the header from the first section.
  - `status_bar()` uses `SPACE[2]` horizontal padding so its left edge aligns
    with the header.
  - Field backgrounds unified to `BG` for entry, listbox, combobox, spinbox,
    and treeview (was platform `#ececec`).
  - Removed hard-coded values: `pack_view_widgets` callers used `pady=2`
    (now `t.SPACE[1]`); `@app.canvas` default `bg="#f0f0f0"` → `t.SURFACE`.
  - Scale and scrollbar thumbs are now a "card" thumb: page-ground fill with
    an `ACCENT` border on a `SURFACE` trough (WCAG 1.4.11 non-text contrast;
    `ACCENT` vs trough 5.3:1, fill vs border 5.9:1). Hover/pressed shift the
    border to the accent ramp.
  - Radio buttons now use the same `indicatormargin` as check buttons so the
    symbol/label spacing matches.

### Fixed

- `tokens.SURFACE` corrected to the Kizashi spec (`#f1ece3`).
- `window_header()` no longer draws a differently-colored area between the
  title and subtitle.

### Tests

- Added `tests/test_ingest_trace.py` (trace updates state, batching, loop
  guard, default lazy-read, `IntVar` keeps Python ints).
- Added Kizashi contrast/`SPACE`-token regressions in `tests/test_tokens.py`
  (scale/scrollbar `UI_PAIRS`), `tests/test_disk_usage_helpers.py`
  (header/status backgrounds and padding), and
  `tests/test_widget_public_api.py` (canvas default bg uses `SURFACE`).

## [0.4.7] — paired gutter logical-line fix

### Fixed

- `Layout.paired(..., line_numbers=True)` gutters numbered **physical**
  (wrapped) rows instead of logical lines. `_reconcile_gutter` /
  `_populate_gutters` used `text.index("end-1c")`, which counts display rows;
  with `wrap="word"`/`"char"` a long wrapped line inflated the gutter count.
  Added `_logical_line_count(text)` which counts newline characters.
- Gutter sync recursion: rewriting a gutter calls `update_idletasks()`, which
  re-enters `_reconcile_gutter`/`_populate_gutters` through the shared
  scrollbar's `yscrollcommand`. Added a per-gutter `_syncing_gutter` guard.
- `on_text_set()` hooks were never cleared by `clear_runtime()`, accumulating
  across re-runs (e.g. swap variants) and running gutter sync multiple times
  per `text_set`. `clear_runtime()` now also clears `_text_set_hooks`.

### Changed

- Documented that `line_numbers=True` takes precedence over `sync_yscroll`:
  enabling `line_numbers` installs a shared scrollbar that always keeps both
  panes and both gutters in lock-step.

## [0.4.6] — section placement fix + layout ergonomics

### Fixed

- `section(..., side=...)` now controls the section frame placement;
  `_pack_section_frame` hardcoded `side="top"`, so a `side="bottom"` section
  declared after an `expand=True` block was pushed off-view and collapsed.
- Child packing decoupled from frame placement: `_Row.child_side` separates
  the section frame's placement side from the side used to pack children
  inside the frame.

### Added

- `examples/bottom_bar_demo.py` — a `side="bottom"` bar pinned below an
  expandable body.

### Known limitation

- `side="bottom"` + focusable children: Tk's `tk_focusNext`/`tk_focusPrev`
  traverse in insertion order, independent of the pack parcel, so focusable
  children in a bottom section land early in the Tab order. Fine for
  non-focusable chrome; planned to generalize `_wire_tab_order`.

## [0.4.5] — Flutter-style layout vocabulary

### Changed

- `Layout.cluster()` renamed to `Layout.wrap()` (Flutter `Wrap` analog);
  `cluster()` kept as a deprecated alias (removed in v0.5.0). Same for
  `LayoutBuilder`. `gap` deprecated in favor of `gapx`/`gapy`.
- `examples/cluster_demo.py` → `examples/wrap_demo.py`;
  `tests/test_cluster.py` → `tests/test_wrap.py`.

### Added

- `nextpytk.types.Flex(name, flex=...)` — a `wrap` child absorbs a share of
  its row's leftover horizontal space (Flutter `Expanded` analog).
- `nextpytk.layout.Constraints` and `FlowDelegate`
  (`compute_positions`/`compute_height`), plus `Layout.flow(*widgets,
  delegate=...)` / `LayoutBuilder.flow(...)` (Flutter `Flow` analog).
- Button styles use `width=0` (cancels clam's `width=-11` min) so button
  width tracks label text.
- `debug_layout()` detects geometry-manager conflicts.

## [0.4.4] — text wrap/h-scroll, public runtime API

### Added

- `wrap=` option to `@app.text` (`Wrap.WORD`/`Wrap.NONE`/`Wrap.CHAR`) and a
  `nextpytk.types.Wrap` typed-constant class.
- `h_scroll=` option to `@app.text` for horizontal scrolling in
  `Wrap.NONE` mode (tracked in `app._text_hscrollbars`).
- `app.layout_frame(name)` — public accessor for the layout (section) frame
  that owns a widget.
- `widget_kwargs: dict[str, Any]` on `CommonWidgetOptions` — per-widget
  design-token overrides applied after construction; invalid/unknown keys
  are ignored.
- `line_numbers=True` to `Layout.paired(...)` with a single shared scrollbar
  keeping panes and gutters in lock-step, plus `app.on_text_set(name, hook)`.
- `Layout.target(name)` + `@app.swap(name, variants=..., default=...)` for
  runtime region switching (HTMX `hx-target`/`hx-swap` analogs) and
  `app.swap_view(name, variant)`.

### Changed

- `TreeviewOptions.double_click` is now typed and honored by `@app.treeview`;
  when `False`, `activate` fires on single `ButtonRelease-1`.
- Added `_validate_choice()`/`_validate_positive_int()` registration-time
  validation for enum-like and positive-int options across decorators.

## [0.4.3] — filepicker + layout blocks

### Added

- `@app.filepicker` (`filedialog` wrapper; `mode=` open/save/directory/open_multiple).
- `Layout(spacing=...)` — layout-wide `SPACE` token default (padx/pady inheritance).
- `Layout.frame(...)` — nested layouts.
- `Layout.cluster(...)` — wrapping flow.
- `Layout.paired(left, right, ..., sync_yscroll=)` — side-by-side panes.

## [0.4.2] — event-sequence generalization + listbox items_key

### Added

- `nextpytk.types.EventSeq` class with common event sequences (`RETURN`,
  `ESCAPE`, `BACKSPACE`, `DELETE`, `TAB`, `DOUBLE_BUTTON_1`–3,
  `LISTBOX_SELECT`). `ListboxEvent` remains a backward-compatible subclass.
- `items_key=` to `@app.listbox` and `values_key=` to `@app.combobox` for
  state-driven choices (symmetric to `treeview`'s `rows_key=`).
- `events=` to `@app.entry` for widget-level event bindings.
- A11y-aware primary mouse-button helpers: `EventSeq.PRIMARY_CLICK`,
  `PRIMARY_DOUBLE_CLICK`, `PRIMARY_BUTTON_RELEASE` (account for left/right
  swap on Windows, macOS, Linux/GNOME).

## [0.4.1] — post-0.4 fixes

### Added

- Text widget ergonomics: `app.text_widget(name)`, `app.text_get(name)`,
  text sync from state via `apply_state`, a11y traits on the real `tk.Text`.
- `font=` to more widget decorators and `padding=` to `@app.entry`.
  Derived per-widget `ttk.Style` is created when a ttk widget rejects
  `-font`/`-padding`.
- Design System section in README covering `Fill`/`Sticky`/`Orient`,
  `SPACE` tokens, and theme helpers.

### Changed

- `TkApp(theme=...)` now accepts `bool | str`: `"kizashi"` (default),
  `"none"`, or another installed ttk theme. `theme=True/False` are
  deprecated (removed in v0.5.0).

### Deprecated

- `col_weights`/`row_weights`/`col_minsizes`/`row_minsizes` (index-order
  plural methods) and `LayoutBuilder.grid(col_weights=, row_weights=)`
  deprecated in favor of the explicit singular API (removed in v0.5.0).

## [0.4.0]

### Added

- Declarative widget registry (`@app.*`): label/status/message, button/entry,
  checkbutton/radiobutton/scale/spinbox, combobox, menubar, text/listbox/
  canvas, treeview, paned, progressbar, bind.
- `Layout` (pack/grid, `.header()`/`.status()` chrome), `@app.multiview`,
  `@app.stages`, `run`/`run_async`/`spawn`/`@app.job`, `schema()`,
  `debug_layout()`, builder registry, a11y choke point `_apply_a11y`.
- Kizashi theme: `tokens` + `apply_theme`/layout helpers with contrast and
  44px target-size regressions.
- PyPI Trusted Publishing on `v*` tag push.

## [0.3.0]

### Added

- Builder registry, headless tests, a11y wiring (`_apply_a11y`), error policy,
  bugfixes. `run_async`/`spawn`/`@app.job`, public runtime API
  (`build_widgets`, `apply_state`, `register_widget_builder`, …).

[Unreleased]: https://github.com/nishimotz/nextpytk/compare/v0.4.8...HEAD
[0.4.8]: https://github.com/nishimotz/nextpytk/compare/v0.4.7...v0.4.8
[0.4.7]: https://github.com/nishimotz/nextpytk/compare/v0.4.6...v0.4.7
[0.4.6]: https://github.com/nishimotz/nextpytk/compare/v0.4.5...v0.4.6
[0.4.5]: https://github.com/nishimotz/nextpytk/compare/v0.4.4...v0.4.5
[0.4.4]: https://github.com/nishimotz/nextpytk/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/nishimotz/nextpytk/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/nishimotz/nextpytk/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/nishimotz/nextpytk/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/nishimotz/nextpytk/releases/tag/v0.4.0
