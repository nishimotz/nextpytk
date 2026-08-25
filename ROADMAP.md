# ROADMAP — nextpytk

> **Note:** Past release history lives in [CHANGES.md](./CHANGES.md).
> This file is the forward-looking plan (near-term, then v0.5.0, then longer term).

## Near term (post-0.4.8)

### A11y

- [ ] `@app.status` live-region behavior (ARIA `aria-live` equivalent / WCAG 4.1.3)
- [ ] Tk 9.1 `tk accessible set_acc_*` real-device verification (9.1b0 + NVDA)
- [ ] Role vocabulary mapping to Tk side
- [x] Automatic `emit_selection_change` / `set_acc_value` (done in 0.4.18 via `sync_map()` IR) — applies to text, value, and selection changes on Tk 9.1+

### Type hints

- [ ] Further TypedDict / Protocol coverage for decorator arguments
- [ ] Fluent API equivalent to `_GridBuilder.columnconfigure`

### Widget expansion

- [ ] Per-widget `bind` for other widgets (`text`, `combobox`, `treeview`, `button`, etc.)
- [ ] `@app.filepicker` — `filedialog` wrapper (schema/tool naming still open)

### Tk 9.0 new widget options

- [ ] `ttk::progressbar -text` — expose the new `-text` option on `@app.progressbar`
- [ ] `$frame -backgroundimage` / `-tile` — expose background-image/tile options on frames
- [ ] `$menu id` — expose menu item `id` option on `@app.menubar` / submenus

### Layout DSL

- [ ] CSS-grid-inspired layout API for 0.5.0: explicit `grid-template-columns` / `grid-template-rows` strings (e.g. `"1fr 2fr"`, `"auto 1fr"`), area-based placement, and gap tokens. Reduce misuse by making rows/columns and widget placement visually aligned in one declaration.
- [ ] Wire visual Tab order for `side="bottom"` sections via `_wire_tab_order` (see v0.4.6 note in CHANGES.md).

### Agent / LLM integration

- [ ] Expose `schema()` as Function Calling definition (bind `sequence`, treeview column defs, etc.)
- [ ] `@agent_tool` integration (GUI operations as agent vocabulary)
- [ ] Surface `@app.filepicker` in `schema()` / tool vocabulary

---

## v0.5.0 — themes / chrome decoupling

- Remove deprecated `theme=True/False` support; `theme` becomes `str` only.
- Remove deprecated `EventSeq.DOUBLE_CLICK`; use `EventSeq.PRIMARY_DOUBLE_CLICK` or `DOUBLE_BUTTON_1`.
- Remove deprecated index-order plural methods `col_weights`/`row_weights`/`col_minsizes`/`row_minsizes` and `Layout.cluster()` alias.
- Decouple `Layout().header()` / `.status()` chrome from Kizashi-specific tokens so they render safely with any ttk theme (`"none"`, `"clam"`, etc.).
- Extract Kizashi as a standalone ttk theme package so it can be proposed upstream or reused independently of nextpytk.

---

## Design direction (from Perl/Tk / SQLAlchemy insights)

nextpytk is not a "Tk reimplementation" (Perl/Tk's trap) — it is a thin layer of state-driven abstraction on top of Tk (HTMX-inspired "state is truth, widgets retained, fragment updates"). The 10-point hint list maps to concrete projects as follows:

- [x] 4. Hand-written `_sync_*` / `_reconcile_*` → declarative IR: `TkApp.sync_map()` (0.4.18).
- [x] 6. Batch API: `TkApp.batch()` + no-op filtering in `apply_state()` (0.4.18).
- [x] 9. A11y as first-class: `apply_state()` auto-emits `set_acc_value` / `emit_selection_change` via `sync_map()` (0.4.18).

Deferred candidates (to schedule into 0.5.0+):

- [ ] 5. Generic fragment swap: unify per-kind sync (`_sync_text_widget` / `_sync_listbox_items` / `_sync_combobox_values`) into a single declarative patch pass driven by `sync_map()` parts, in the spirit of `hx-swap`. The existing `app.swap()` / `swap_view()` already provide region-level swap; this item targets content-level fragment updates.
- [ ] 8. Event loop modernization: merge the blocking `mainloop()` path and the cooperative `async_mainloop()` behind a single user-facing surface, and document/relax the current constraint that asyncio tasks must not touch Tk directly (must marshal via `async_poll` / `after`).
- [ ] 7. Compiled command caching: reuse structure-identical Tcl calls (`configure`, `delete`, `insert`, treeview `insert`) as pre-built `Tcl_Obj` argument vectors instead of re-parsing Python strings per call. Layer on top of 6 (batch) and 4 (IR) so the IR nodes carry the command templates.

---

## Longer term

##Remove deprecated `Layout().grid().widget(...)`; use `Layout().grid().cell(...)` instead.
- # ttk Style layer

- [ ] `Layout.style("my_button", background=..., font=...)` style definitions

### Declarative components

- [ ] `@app.component` decorator (React-like reuse, replacing `Layout`)
- [ ] State type definitions and validation (no Pydantic)

### Testing

- [ ] WidgetSpec unit tests
