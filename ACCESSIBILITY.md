# Accessibility Statement — nextpytk

nextpytk is built around the idea that accessible Tkinter applications should be
the default, not an afterthought. This statement describes what we aim for, what
is supported today, what is known to be broken or unverified, and how to report
problems.

## Goals

- Let developers produce keyboard-operable desktop applications without writing
  accessibility plumbing by hand.
- Expose `role` and `description` metadata for every registered widget, kept in
  one place and exported through `schema()`.
- Work with screen readers on Windows (NVDA), macOS (VoiceOver), and Linux
  (Orca) through native Tk widgets and Tk's accessibility attributes.
- Make state changes announced, not only visible.

## Supported environments

| Component | Supported |
| --- | --- |
| Python | 3.13 and later |
| Tk | 8.6 (standard in CPython builds) and 9.1+ |
| Widgets | `ttk` where available, `tk` otherwise |
| OS | Windows, macOS, Linux (Tk-dependent) |

Accessibility attribute emission (`set_acc_value`, `emit_selection_change`) is
implemented for **Tk 9.1+**. On Tk 8.6 those attributes do not exist, and what
the screen reader announces depends entirely on the platform and assistive
technology.

## Known barriers

These are current limitations, not aspirations. Each one is tracked in
[ROADMAP.md](./ROADMAP.md).

- **Tk 9.1 accessibility attributes are not verified on real hardware.** The
  `tk accessible set_acc_*` path has not been confirmed with a real screen
  reader (Tk 9.1b0 + NVDA verification is still open).
- **Role vocabulary is not mapped to Tk yet.** `role` values exist in the
  schema, but the Tk-side mapping is undecided, so roles may not change what an
  assistive technology announces.
- **`@app.status` is not a live region.** It sets `role="status"` metadata, but
  equivalent ARIA `aria-live` behavior (WCAG 4.1.3) is not implemented. Status
  text changes may not be announced automatically.
- **No automatic announcements on Tk 8.6.** Without `set_acc_value` /
  `emit_selection_change`, value and selection changes must be communicated
  through visible and focusable UI.
- **Disabled `Listbox` widgets** receive `selectmode="none"` instead of being
  fully disabled, so programmatic updates keep working. Keyboard users cannot
  select items, but the widget is not announced as disabled by all screen
  readers.
- **Focus order** follows widget registration and layout order. Custom layouts
  are not audited for tab order.

## What contributors should do

- Give every new widget a `role` and a `description`. A widget without a
  meaningful name is an accessibility defect.
- Do not introduce layouts that keyboard users cannot reach. Every interactive
  element must be reachable with Tab.
- Do not rely on color, position, or pointer-only interaction to convey state.
- When changing accessibility behavior, add an entry to
  [CHANGES.md](./CHANGES.md) and update this statement or ROADMAP.md.
- Include accessibility tests where behavior can be checked headlessly.

## Reporting an accessibility problem

Open an issue at <https://github.com/nishimotz/nextpytk/issues> and include:

- The assistive technology and version (for example, NVDA 2025.1, VoiceOver on
  macOS 15.8)
- OS and version
- Python version and Tk version (`python -c "import tkinter; print(tkinter.TkVersion)"`)
- A minimal reproduction: the `TkApp` definition and the steps to trigger the
  problem
- What was announced versus what you expected

Please use the `a11y` label. Reports without a reproduction are hard to act on;
a short code snippet is enough.
