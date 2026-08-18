# Changelog

All notable changes to nextpytk are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.17] — 2026-08-18

### Added

- `@app.entry` placeholder now uses Tk 9.0's native `-placeholder` /
  `-placeholderforeground` options when available (detected at build time via
  `_try_native_placeholder`). The native placeholder is shown only when the
  entry is empty and unfocused, and is never written into the `StringVar`, so
  the effective value stays clean. On Tk 8.6 the previous manual
  prefill-and-recolor fallback (`_setup_manual_placeholder`) is used unchanged.
- Documented in `theme.py` that the Kizashi look-and-feel is built on the
  `clam` ttk theme (a cross-platform, self-drawn theme that honors custom
  colors/borders), and corrected the misleading "only built-in theme" comment
  to note that `alt` also honors overrides but with fewer widget definitions.
- Added a "Tk 9.0 new widget options" section to `ROADMAP.md` tracking
  `ttk::progressbar -text`, `$frame -backgroundimage`/`-tile`, and `$menu id`.

### Changed

- `_entry_effective_value`, `_entry_focus_in`, `_entry_focus_out`, and
  `_apply_entry_value_after_state` now early-return when a native placeholder
  is active, since Tk manages the placeholder independently of the variable.

## [0.4.16] — 2026-08-15

### Changed

- Refactored monolithic `app.py` into cohesive internal subsystems while maintaining 100% backward compatibility of all public APIs and 352 test cases:
  - `a11y/` (`A11yEngine`): Accessibility choke point and TIP 733 / Tk 9.1+ attribute management.
  - `schema/` (`SchemaExporter`): JSON schema generation for introspection and tooling.
  - `async_engine/` (`AsyncEngine`): Asyncio event loop integration, `@app.job`, `spawn()`, and cooperative async main loop runner.
  - `state/` (`StateStore`): Reactive state storage, Tcl write trace ingestion, and Levenshtein validation.
  - `widget_ops/` (`WidgetRegistrationMixin`, `WidgetBuildersMixin`, `EventHandlersMixin`): Declarative widget registration DSL, Tkinter/ttk widget construction, and GUI event dispatchers.
  - `app.py`: Streamlined `TkApp` facade coordinating the modular subsystems.

### Fixed

- Core `tk` fallback widgets (`text`, `listbox`, `canvas`) now resolve their
  colors from the active `ThemeTokens` instead of the frozen `KIZASHI_LIGHT`
  module constants, so dark mode and custom themes apply consistently.
- `@app.message` now uses `ttk.Label` with `wraplength` (auto-wrap) instead of
  the legacy `tk.Message` widget, so it inherits the active ttk theme.

### Added

- `examples/matplotlib_demo.py` demonstrating the official pattern for
  embedding a Matplotlib `FigureCanvasTkAgg` into a `Layout.container()`
  slot, with a `@app.scale` driving the plot reactively.
- `matplotlib` optional dependency (`pip install nextpytk[matplotlib]` /
  `uv run --extra matplotlib`) and a `make run-matplotlib` target.
- `examples/svg_demo.py` demonstrating SVG image loading via `tk.PhotoImage`
  (Tk 9.0+), with a runtime version guard that exits cleanly on Tk 8.6.

## [0.4.15] — 2026-08-14

### Added

- `TkApp.add_*` direct widget registration methods: `add_label`, `add_status`,
  `add_message`, `add_button`, `add_entry`, `add_checkbutton`, `add_radiobutton`,
  `add_text`, `add_scale`, `add_spinbox`, `add_combobox`, `add_listbox`,
  `add_treeview`, `add_canvas`, `add_filepicker`, and `add_progressbar`.
  These allow registering widgets without boilerplate dummy callback functions
  (e.g. ``def on_name(): return {}`` is no longer needed for read-only or
  button-driven entries and static labels).
- `ViewContext` (``with app.view(...) as v:``) now proxies all ``add_*`` methods.
- `TkApp.get_widget(name)` added as an explicit alias for `TkApp.widget(name)`
  to provide a clear, first-class escape hatch for accessing underlying
  `tk.Widget` / `ttk.Widget` instances.
- `TkApp.eval(script)`, `TkApp.call(*args)`, and `TkApp.tcl` added to expose
  direct access to the embedded Tcl interpreter underneath Tkinter as a first-class
  escape hatch for high-performance scripting and low-level Tcl commands.
- `content=` option for `@app.text` and `add_text` to set initial text content
  declaratively during widget registration.
- `treeview` column definitions now support simple string sequences
  (e.g. `columns=["id", "name"]`), automatically converting them to column headers.
- `ThemeTokens` dataclass and built-in `KIZASHI_LIGHT` and `KIZASHI_DARK` themes.
  `TkApp(theme="kizashi-dark")` or `TkApp(theme=custom_theme)` allows type-safe
  color palette customization and dark mode out of the box.
- Decoupled `layout.py` and `app.py` frame background colors from hard-coded tokens,
  now dynamically resolving from active `ThemeTokens` and Option Database.
- `TkApp.load_theme_tcl(script_or_path, theme_name)` method to load external Tcl /
  ttk theme scripts or `.tcl` theme files (e.g. Azure, Sun Valley).
- `TkApp.theme_tokens` property to inspect the active theme token set.
- `sync=False` option for widget registration to opt out of reactive state
  synchronization (preventing `apply_state` from overwriting imperatively managed
  contents such as log streams or custom drawings).
- `Layout.container(name)` and `GridBuilder.container(name)` to reserve unmanaged
  `tk.Frame` slots with consistent theme margins for embedding raw Tkinter controls,
  Matplotlib canvases (`FigureCanvasTkAgg`), or external GUI components.
- `TkApp.container(name)` convenience method to retrieve unmanaged container frames.
- `TkApp.untracked()` context manager to temporarily suppress reactive trace listeners
  and state updates during high-throughput batch operations.

### Documentation

- Added "Escape Hatches (Interoperating with Raw Tkinter)" guide to READMEs
  explaining how to access raw Tkinter widgets (`app.widget()`, `app.get_widget()`,
  `Layout().grid().cell_raw()`, `Layout.container()`, `sync=False`, `app.untracked()`,
  `app.root`, `app.eval()`, `app.call()`, and `app.tcl`).
- Added "Customizing Themes & Design Tokens" guide to READMEs detailing dark mode,
  `ThemeTokens` customizations, and `load_theme_tcl`.
- Added "When to use nextpytk" architectural guidance to clarify sweet spots
  (forms, settings, dashboards, LLM agents, a11y apps) and distinguish them from
  canvas-heavy / game-loop use cases.

## [0.4.14] — 2026-08-13

### Added

- `Layout().grid().cell_raw(widget, *, sticky, padx, pady, colspan, rowspan)`
  places a raw `tk.Widget` instance directly into a grid cell. Unlike `cell()`
  which takes a registered widget name, `cell_raw()` accepts an already-created
  widget — useful for mixing nextpytk's declarative widgets with hand-built
  tkinter frames or controls.

### Fixed

- `pyproject.toml` Changelog URL now points to `CHANGES.md` (was `ROADMAP.md`).

## [0.4.13] — 2026-08-11

### Added

- `Layout().grid().cell(...)` places one or more widgets in horizontally
  consecutive cells. `cell("a")` is equivalent to `widget("a")`, and
  `cell("a", "b", "c")` places three widgets in a single row from the current
  cursor position with shared options (e.g. `sticky`, `padx`, `pady`).

### Changed

- `Layout().grid().widget(...)` is now deprecated. It continues to work and
  emits a `DeprecationWarning`. Use `cell(...)` instead. (Note:
  `app.widget(name)` — the getter that returns a built widget — is unaffected
  and remains supported.)

## [0.4.12] — 2026-08-09

### Added

- `on_resize` hook: `run()`, `run_async()`, `run_stages()`, and
  `run_multiview()` now accept an `on_resize(width, height)` callback that
  fires whenever the window is resized. The framework manages the underlying
  Tk `<Configure>` binding so app developers do not have to hand-roll it.
  Three guarantees make it safe to reconfigure widgets from the callback:
  - **Toplevel only**: child-widget `<Configure>` events are ignored, so
    reconfiguring a child cannot re-trigger the handler.
  - **Size-change only**: the callback fires only when the window's
    `(width, height)` actually changed, so a callback that calls
    `configure`/`pack_configure` (which can emit `<Configure>` without
    changing the toplevel size) does not loop.
  - **Debounced**: rapid resize storms are coalesced into a single callback
    via `after`, so the callback runs at most once per settle window.

## [0.4.11] — 2026-08-08

### Added

- `TkApp.unregister(name)` removes a registered widget spec by name, returning
  `True`/`False`. Useful in interactive sessions to drop a widget (and its
  callback) before `run()`, e.g. to re-declare it with a different kind or
  options.
- Padding debug overlay: pass `debug_padding=True` to `TkApp` (or call
  `app.show_debug_padding(True)` / `(False)`) to place small colored badges
  over the layout. Three kinds of padding are color-coded: **section-frame
  outer padding** (yellow, `section padx 8 / pady 12`), **widget's own outer
  padding** (cyan, `widget padx 15 / pady 20`), and **widget inner padding**
  (orange, `inner padx 8 / pady 12` — a label's `padding` option or a text
  widget's `padx`/`pady`). The badges are `place`-managed labels over the
  root, so they never disturb the pack/grid layout, and they re-place
  themselves on window resize. Section badges report the widget names they
  group (e.g. `section[title,body]`). The `inner` badge is placed just inside
  the widget's bottom edge so it reads as "inside" the widget rather than
  stacked with the section/widget badges at the top-left; for a `text` widget
  it aligns with the first character's top-left corner (offset by the text's
  `padx`/`pady`). Hidden widgets (via
  `app.hide()`) are excluded from the overlay, so a no-longer-visible widget
  leaves no stale badge. `app.show()` / `app.hide()` automatically re-place
  the badges, so
  dynamic visibility changes stay in sync without an explicit refresh. While
  either overlay is active, a 1-second poll re-places the badges whenever any
  widget's position actually moves (so layout shifts not surfaced to the
  framework's hooks still track). `app.refresh_debug_overlay()` is still
  available to force a re-read; it defers the rebuild to the idle task so
  badges land at the widget's *final* positions after `pack`/`grid` settle.
  Also added
  `app.widget_padding(name)` to read a built widget's own layout padding.
- Layout-debug overlay: `app.show_debug_layout(True)` / `(False)` renders each
  widget's `debug_layout()` JSON info as a badge at the widget's own location
  — the visual, in-window counterpart of `debug_layout()` (geometry, requested
  size, and pack/grid details). Re-places on resize (debounced).
- `app.set_page_margin(margin)` updates the outer `content_frame` page pad at
  runtime, so a resize handler can re-scale it proportionally (e.g. to window
  height). This complements `Layout(page_margin=...)`, which sets the initial
  value.
- The padding debug overlay (`show_debug_padding`) now also badges the
  outermost page margin (a green `page padx 8 / pady 8` badge on the
  `content_frame`), so the outer safe area is visible alongside the
  section/widget/inner badges.
- `debug_layout()` now includes each widget's `padx`/`pady` in its
  `pack_info` / `grid_info` payloads.
- `app.layout_info()` is the canonical, non-`debug`-named accessor for the
  runtime layout snapshot (geometry, requested size, pack/grid details). It
  aligns with tkinter's `pack_info()` / `grid_info()` convention and pairs with
  `schema()` (content vs. presentation).
- `Layout.section()` accepts an optional `name=` so a section frame can be
  addressed at runtime with `app.hide_section(name)` / `app.show_section(name)`
  — useful for hiding an entire section (and the empty space it reserved), e.g.
  swapping between a diagram and a code block. When `name=` is omitted, the
  section is registered under an auto-derived name `<first widget>_section`
  (e.g. `diagram_section`).
- `app.hide_section(name)` / `app.show_section(name)` hide or restore a whole
  section frame at runtime, keeping its pack options so `show_section` restores
  it exactly. Unlike `app.hide(name)` (which removes a single widget), these
  remove the entire section frame including its reserved space.
- The padding debug overlay is enabled automatically at startup when the
  `NEXTPYTK_DEBUG_PADDING` environment variable is set to a non-empty value
  other than `0`, so any app can be inspected without editing its source. This
  works across all run modes (`run()`, `run_multiview()`, `run_stages()`,
  `run_async()`).
- Padding / debug-layout badges now show `side` / `fill` / `expand` / `anchor`
  pack hints on the badge text (single line), and use the app font rather than
  a raw `TkDefaultFont` tuple. Badges also skip widgets that are not currently
  mapped (e.g. inactive multiview tabs), so no stray badge appears over a
  hidden tab.

### Changed

- `app.debug_layout()` is now a **deprecated alias** for `app.layout_info()`.
  It will be removed in 0.5.x; prefer `layout_info()`.
- Re-registering a widget name (e.g. re-decorating `@app.button("next")` in an
  interactive session) now silently replaces the previous spec in place instead
  of raising `ValueError`. The latest definition wins. `bind` specs are still
  exempt: a bind sharing a button's name remains the documented shortcut
  pairing and never replaces a widget spec.
- `Layout` accepts a `page_margin` option that overrides the outer
  `content_frame` page pad (default `SPACE[6]` / 24px). Pass `page_margin=0`
  to make a top-level layout hug the window edge; the per-block
  `padx`/`pady` still apply.
- `_relax_minsize()` no longer pins the window to a fixed `WxH` geometry. It
  now resets the explicit geometry (`geometry("")`) after lowering the
  minimum, so a small app still opens at its requested size but the window
  keeps following its content — e.g. a button label that widens at runtime no
  longer gets clipped.
- `_warn_orphan_layout_names()` no longer flags `Layout.frame(name, ...)` /
  `Layout.target(name, ...)` container names as orphaned widgets. It now uses
  `Layout.widget_names()`, which correctly excludes self-mounted frame/swap
  region names and only reports actual widget names.

### Tests

- `tests/test_text.py`: `test_relax_minsize_does_not_pin_window_size` (after
  relax, growing a button label grows the window's requested width instead of
  clipping it).
- `tests/test_api.py`: `test_layout_names_excludes_nested_frame_name` (a
  `frame(name, ...)` container name is not flagged as an orphan).
- `tests/test_layout_spacing.py`:
  `test_layout_page_margin_default_is_space6`,
  `test_layout_page_margin_zero`,
  `test_layout_page_margin_explicit` (the outer `content_frame` page pad is
  overridable via `Layout(page_margin=...)`),
  `test_set_page_margin_updates_runtime` (`app.set_page_margin()` re-scales
  the page pad at runtime).
- `tests/test_errors.py`:
  `test_duplicate_widget_name_replaces_in_place`,
  `test_re_register_same_kind_replaces_callback`,
  `test_unregister_removes_spec`,
  `test_unregister_then_re_register` (re-registering replaces in place;
  `app.unregister(name)` removes a spec).
- `tests/test_debug_layout.py`:
  `test_show_debug_padding_badges_padded_frames` (badges placed on section
  frames that carry padding),
  `test_show_debug_padding_toggle_off_removes_badges`,
  `test_widget_padding_reports_layout_padding`,
  `test_show_debug_padding_reports_inner_padding` (label `padding` and text
  `padx`/`pady` inner badges),
  `test_show_debug_padding_reports_self_padding` (cyan self badge for a widget
  packed with explicit `padx`/`pady`),
  `test_show_debug_padding_section_badge_lists_widgets`,
  `test_show_debug_padding_rebuilds_after_set_padding`,
  `test_show_debug_padding_toggle_off_unbinds_resize`,
  `test_show_debug_layout_badges_render_json_info`,
  `test_show_debug_layout_toggle_off`,
  `test_debug_badges_clickable_to_lift`,
  `test_refresh_debug_overlay_rebuilds_active_badges`,
  `test_refresh_debug_overlay_noop_when_inactive`,
  `test_debug_badges_skip_hidden_widgets`,
  `test_debug_overlay_periodic_poll_moves_badges`,
  `test_debug_overlay_poll_cancelled_when_off`,
  `test_inner_badge_placed_inside_widget`,
  `test_inner_badge_text_aligns_first_character`,
  `test_show_debug_padding_shows_page_margin_badge`,
  `test_show_debug_padding_page_badge_tracks_set_page_margin`.

## [0.4.10] — 2026-08-07

### Added

- `@app.text` accepts `scrollbar=False` to omit the vertical scrollbar. The
  text widget is built and wired up (content set/read via `text_set` /
  `text_get` still work) but no vertical scrollbar is created. Useful for
  read-only, single-purpose text panes — e.g. a borderless code listing in a
  slide deck — that should render as a plain surface without a scrollbar.
- `app.show(name)` / `app.hide(name)` runtime helpers toggle a widget's
  visibility without losing its layout geometry. `hide` removes the widget
  from its section (via `grid_remove` / `pack_forget`) and remembers it, so a
  later `apply_state`/`sync` does not repack it; `show` restores it to its
  original grid cell or pack options. `app.is_visible(name)` reports the
  current mapped state. Both are safe to call on already-hidden/visible
  widgets and on widgets that have not been built yet. This replaces the
  manual `winfo_manager()` + `grid_remove()` dance.
- `app.set_padding(name, padx=..., pady=...)` dynamically changes a built
  widget's layout padding. It is **hide-aware**: while a widget is hidden the
  change is remembered and applied when `show()` restores it, instead of
  calling `pack_configure` on a `pack_forget`'d widget (which would silently
  re-show it). This makes resize-driven padding updates safe in apps that
  also toggle a widget's visibility.

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
- `tests/test_text.py`:
  `test_text_without_scrollbar_has_no_vscrollbar` (scrollbar=False omits the
  vertical scrollbar while the text widget stays usable),
  `test_text_scrollbar_defaults_to_present` (vertical scrollbar present by
  default),
  `test_hide_removes_widget_and_show_restores_packed`,
  `test_hide_show_gridded_widget_preserves_cell`,
  `test_hide_show_idempotent` (app.show/hide toggle visibility while
  preserving layout geometry; no-op when idempotent).
  `test_set_padding_visible_applies_immediately`,
  `test_set_padding_hidden_applies_on_show` (set_padding must not re-pack a
  hidden widget; the change is applied on show),
  `test_set_padding_gridded` (padding applied via grid_configure).
  (FilepickerCallback exports the concrete single-arg signature).

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
