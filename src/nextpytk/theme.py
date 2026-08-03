# -*- coding: utf-8 -*-
"""
Kizashi theme setup for ttk. Call apply_theme(root) once, right after
creating the root window and before building any widgets.
"""

import sys
import tkinter as tk
from tkinter import ttk

from . import tokens as t

# Shared internal padding for all ttk button variants (TButton, Primary, Secondary).
# 16x12 + h5 (15px) keeps the requested height above MIN_TARGET (44px, WCAG 2.5.5)
# across macOS/Windows default fonts without forcing every button section to
# reserve 60+ px. Declared once here so the three button styles stay in lock-step.
_BUTTON_PADDING = (t.SPACE[4], t.SPACE[3])  # (16, 12)


def apply_theme(root):
    """Configure ttk styles from the Kizashi tokens. Call once on root."""
    # Ensure FONT_FAMILY is resolved against the real font list now that Tk
    # is initialized.  If nextpytk was imported before tk.Tk(), it may have
    # fallen back to TkDefaultFont and produced undersized labels/buttons.
    t.resolve_font_family()

    style = ttk.Style(root)

    # 'clam' is the only built-in theme that honors custom colors/borders
    # consistently across platforms.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=t.BG)

    # Apply the ::selection and keyboard focus colors to core tk widgets
    # (Text, Listbox, Entry). highlightColor is the classic-tk focus indicator
    # (WCAG 2.4.7 Focus Visible). Option-database settings affect widgets
    # created afterwards.
    root.option_add("*selectBackground", t.SELECTION_BG)
    root.option_add("*selectForeground", t.SELECTION_FG)
    root.option_add("*highlightColor", t.FOCUS)

    # --- base -------------------------------------------------------------
    style.configure(".", background=t.BG, foreground=t.TEXT, font=t.font("body"))
    style.configure("TFrame", background=t.BG)
    style.configure("Surface.TFrame", background=t.SURFACE)

    style.configure("TLabel", background=t.BG, foreground=t.TEXT, font=t.font("body"))
    style.configure("Heading.TLabel", font=t.font("h3"))
    style.configure("Subheading.TLabel", font=t.font("h5"))
    style.configure("Muted.TLabel", foreground=t.TEXT_MUTED, font=t.font("body"))
    style.configure("FieldLabel.TLabel", foreground=t.NEUTRAL[700], font=t.font("small"))

    # --- divider (strong 2px rule) ----------------------------------------
    style.configure("Divider.TSeparator", background=t.DIVIDER)

    # --- entries ------------------------------------------------------------
    style.configure(
        "TEntry",
        fieldbackground=t.SURFACE,
        foreground=t.TEXT,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        borderwidth=1,
        relief="solid",
        padding=(t.SPACE[2], t.SPACE[2] - 2),
        insertcolor=t.TEXT,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", t.FOCUS), ("hover", t.NEUTRAL[600])],
        lightcolor=[("focus", t.FOCUS)],
        darkcolor=[("focus", t.FOCUS)],
    )

    # --- buttons ------------------------------------------------------------
    # Primary = borderless ACCENT with ON_ACCENT text, hover ACCENT_HOVER;
    # secondary = white card with accent border, hover surface.
    # padding 16x12 + 15px h5 keeps the requested height above MIN_TARGET
    # (44px, WCAG 2.5.5) across macOS/Windows default fonts, without forcing every
    # button section to reserve 60+ px.  borderwidth=SPACE[2] (8px) draws the
    # native ttk focus ring well inside the border so it does not sit on the
    # edge (WCAG 2.4.7 Focus Visible).
    # ``width=0`` cancels clam's default ``width=-11`` (a minimum of 11 text
    # characters ~182px) so button width tracks the label instead of being
    # locked to a minimum. In a grid, ``col_weight`` provides uniform width;
    # in a cluster, each button keeps its natural text width.
    style.configure(
        "TButton",
        font=t.font("h5", weight="bold"),
        borderwidth=t.SPACE[2],
        relief="solid",
        padding=_BUTTON_PADDING,
        bordercolor=t.NEUTRAL[500],
        anchor="center",
        width=0,
    )
    style.map(
        "TButton",
        bordercolor=[
            ("active", t.NEUTRAL[600]),
            ("pressed", t.NEUTRAL[700]),
            ("focus", t.FOCUS),
        ],
    )
    style.configure(
        "Primary.TButton",
        font=t.font("h5", weight="bold"),
        relief="solid",
        padding=_BUTTON_PADDING,
        background=t.ACCENT, foreground=t.ON_ACCENT, bordercolor=t.ACCENT,
        borderwidth=t.SPACE[2],
        focuscolor=t.ON_ACCENT,
        anchor="center",
        width=0,
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", t.ACCENT_PRESSED), ("active", t.ACCENT_HOVER),
                    ("focus", t.ACCENT)],
        foreground=[("focus", t.ON_ACCENT)],
        bordercolor=[("pressed", t.ACCENT_PRESSED), ("active", t.ACCENT_HOVER),
                    ("focus", t.ACCENT)],
    )
    style.configure(
        "Secondary.TButton",
        font=t.font("h5", weight="bold"),
        relief="solid",
        padding=_BUTTON_PADDING,
        background=t.CARD, foreground=t.TEXT, bordercolor=t.ACCENT,
        borderwidth=t.SPACE[2],
        anchor="center",
        width=0,
    )
    style.map(
        "Secondary.TButton",
        background=[("pressed", t.NEUTRAL[300]), ("active", t.SURFACE)],
        bordercolor=[
            ("active", t.ACCENT_HOVER),
            ("pressed", t.ACCENT_PRESSED),
            ("focus", t.FOCUS),
        ],
    )

    # --- notebook -----------------------------------------------------------
    # Give the tab row a small horizontal margin so the first/last tab borders
    # are not clipped by the notebook edge.
    style.configure("TNotebook", background=t.BG, tabmargins=(t.SPACE[1], t.SPACE[1], t.SPACE[1], t.SPACE[1]))
    style.configure(
        "TNotebook.Tab",
        background=t.NEUTRAL[200],
        foreground=t.TEXT,
        font=t.font("small", weight="bold"),
        padding=(t.SPACE[3], t.SPACE[2]),
        uniform="tabs",
        # No hard-coded width: the multiview setup fits the tab width to
        # the longest view label via tkinter.font.measure, so the tab
        # area never crops long names and never wastes space for short
        # ones. The default ``uniform="tabs"`` keeps all tabs the same
        # width within one notebook.
        anchor="w",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", t.BG), ("active", t.NEUTRAL[300])],
        foreground=[("selected", t.TEXT)],
        # Selected tab gets a little extra vertical padding so it does not
        # shrink visually when the default clam theme removes its expansion.
        padding=[("selected", (t.SPACE[3], t.SPACE[4]))],
    )

    # --- check / radio ----------------------------------------------------
    # Padding increases the ttk layout box around the indicator + label so the
    # effective click/tap target is larger and neighbouring controls don't feel
    # cramped. The indicator itself stays its native size; WCAG 2.5.5 is best met
    # by touch-friendly surrounding space rather than scaling the glyph.
    # Use the same (16,12) as buttons so check/radio align visually with
    # buttons in a cluster row.
    _check_radio_padding = (t.SPACE[4], t.SPACE[3])  # (16, 12), matches buttons
    style.configure(
        "TCheckbutton",
        background=t.BG,
        foreground=t.TEXT,
        font=t.font("body"),
        focuscolor=t.FOCUS,
        padding=_check_radio_padding,
        # clam's checkbutton gap between indicator and label is driven by
        # ``indicatormargin`` (default "0.75p 0.75p 3p 0.75p"; right=3px).
        # ``indicatorpadding`` is ignored by clam, so widen the right margin
        # to SPACE[2] (8px) for a cleaner indicator/text separation.
        indicatormargin=(0, 0, t.SPACE[2], 0),
    )
    style.layout(
        "TCheckbutton",
        [
            (
                "Checkbutton.padding",
                {
                    "sticky": "w",
                    "children": [
                        ("Checkbutton.indicator", {"side": "left", "sticky": ""}),
                        (
                            "Checkbutton.focus",
                            {
                                "side": "left",
                                "sticky": "w",
                                "children": [
                                    ("Checkbutton.label", {"sticky": "w"}),
                                ],
                            },
                        ),
                    ],
                },
            ),
        ],
    )
    style.configure(
        "TRadiobutton",
        background=t.BG,
        foreground=t.TEXT,
        font=t.font("body"),
        focuscolor=t.FOCUS,
        padding=_check_radio_padding,
    )
    style.layout(
        "TRadiobutton",
        [
            (
                "Radiobutton.padding",
                {
                    "sticky": "w",
                    "children": [
                        ("Radiobutton.indicator", {"side": "left", "sticky": ""}),
                        (
                            "Radiobutton.focus",
                            {
                                "side": "left",
                                "sticky": "w",
                                "children": [
                                    ("Radiobutton.label", {"sticky": "w"}),
                                ],
                            },
                        ),
                    ],
                },
            ),
        ],
    )

    # --- scale --------------------------------------------------------------
    style.configure(
        "TScale",
        background=t.BG,
        troughcolor=t.SURFACE,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        padding=(t.SPACE[1], t.SPACE[2]),
    )

    # --- spinbox ------------------------------------------------------------
    style.configure(
        "TSpinbox",
        fieldbackground=t.SURFACE,
        foreground=t.TEXT,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        arrowcolor=t.ACCENT,
        borderwidth=1,
        relief="solid",
        padding=(t.SPACE[2], t.SPACE[2]),
        insertcolor=t.TEXT,
    )
    style.map(
        "TSpinbox",
        bordercolor=[("focus", t.FOCUS), ("hover", t.NEUTRAL[600])],
        lightcolor=[("focus", t.FOCUS)],
        darkcolor=[("focus", t.FOCUS)],
        arrowcolor=[("active", t.ACCENT_HOVER), ("pressed", t.ACCENT_PRESSED)],
    )

    # --- combobox -----------------------------------------------------------
    style.configure(
        "TCombobox",
        fieldbackground=t.SURFACE,
        foreground=t.TEXT,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        arrowcolor=t.ACCENT,
        borderwidth=1,
        relief="solid",
        padding=(t.SPACE[2], t.SPACE[2]),
        insertcolor=t.TEXT,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", t.FOCUS), ("hover", t.NEUTRAL[600])],
        lightcolor=[("focus", t.FOCUS)],
        darkcolor=[("focus", t.FOCUS)],
        arrowcolor=[("active", t.ACCENT_HOVER), ("pressed", t.ACCENT_PRESSED)],
        fieldbackground=[("readonly", t.SURFACE), ("active", t.SURFACE)],
        selectbackground=[("focus", t.ACCENT_RAMP[200])],
        selectforeground=[("focus", t.TEXT)],
    )

    # macOS Aqua renders the read-only combobox selection with a strong
    # native highlight that can override the regular foreground color and
    # leave white text on a very light field. Give read-only comboboxes a
    # dedicated style with a darker field and an explicit dark selection
    # foreground so the current value stays readable.
    style.configure(
        "Readonly.TCombobox",
        fieldbackground=t.NEUTRAL[100],
        foreground=t.TEXT,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        arrowcolor=t.ACCENT,
        borderwidth=1,
        relief="solid",
        padding=(t.SPACE[2], t.SPACE[2]),
        insertcolor=t.TEXT,
    )
    style.map(
        "Readonly.TCombobox",
        bordercolor=[("focus", t.FOCUS), ("hover", t.NEUTRAL[600])],
        lightcolor=[("focus", t.FOCUS)],
        darkcolor=[("focus", t.FOCUS)],
        arrowcolor=[("active", t.ACCENT_HOVER), ("pressed", t.ACCENT_PRESSED)],
        fieldbackground=[("readonly", t.NEUTRAL[100]), ("active", t.NEUTRAL[100])],
        selectbackground=[("focus", t.ACCENT_RAMP[300])],
        selectforeground=[("focus", t.TEXT)],
        foreground=[("readonly", t.TEXT), ("active", t.TEXT)],
    )

    # --- progressbar --------------------------------------------------------
    style.configure(
        "TProgressbar",
        background=t.ACCENT,
        troughcolor=t.SURFACE,
        bordercolor=t.DIVIDER,
        lightcolor=t.DIVIDER,
        darkcolor=t.DIVIDER,
        borderwidth=0,
    )
    style.map(
        "TProgressbar",
        background=[("active", t.ACCENT_HOVER)],
    )

    # --- scrollbar ----------------------------------------------------------
    style.configure(
        "TScrollbar",
        background=t.NEUTRAL[300],
        troughcolor=t.SURFACE,
        bordercolor=t.DIVIDER,
        arrowcolor=t.TEXT,
        gripcount=0,
        borderwidth=0,
    )
    style.map(
        "TScrollbar",
        background=[("active", t.NEUTRAL[400]), ("pressed", t.NEUTRAL[500])],
        arrowcolor=[("active", t.TEXT), ("pressed", t.TEXT)],
    )

    # --- treeview -----------------------------------------------------------
    style.configure(
        "Treeview",
        background=t.BG,
        foreground=t.TEXT,
        fieldbackground=t.BG,
        font=t.font("body"),
        rowheight=t.SPACE[8],  # 16px body font line with descender clearance
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=t.SURFACE,
        foreground=t.TEXT,
        font=t.font("small", weight="bold"),
        borderwidth=0,
        relief="flat",
        padding=t.SPACE[2],
    )
    style.map(
        "Treeview",
        background=[("selected", t.ACCENT_RAMP[100])],
        foreground=[("selected", t.ACCENT_RAMP[700])],
    )

    return style


def _set_windows_dpi_aware():
    """Opt into system-DPI awareness before creating any Tk windows on Windows.

    This makes Tkinter respect the display scaling factor on Windows,
    otherwise widgets, fonts, and the window chrome render at 96-DPI logical
    pixels and look blurry or too small on high-DPI displays.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from typing import Any, cast
        _ctypes: Any = cast(Any, ctypes)
        windll: Any = _ctypes.windll
        # Windows 10 1703+ per-monitor v2 (preferred)
        try:
            awareness = ctypes.c_int(-4)  # PROCESS_PER_MONITOR_DPI_AWARE_V2
            windll.user32.SetProcessDpiAwarenessContext(awareness)
            return
        except Exception:
            pass
        # Windows 10 1607+ per-monitor
        try:
            windll.shcore.SetProcessDpiAwareness(2)  # PerMonitor
            return
        except Exception:
            pass
        # Fallback for Windows 8.1/10 up to 1607
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


def configure_window(root, title, min_width=380, min_height=260, resizable=True):
    """Apply consistent window chrome: background, title, sizing, margins.

    Sets a light title bar on Windows to match the light theme background.
    """
    root.title(title)
    root.configure(bg=t.BG)
    root.minsize(min_width, min_height)
    root.resizable(resizable, resizable)

    if sys.platform.startswith("win"):
        try:
            import ctypes
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())  # type: ignore[attr-defined]
            value = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(  # type: ignore[attr-defined]
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:
            pass


def content_frame(root, padding=None):
    """Standard outer container with the standard page margin."""
    pad = t.SPACE[6] if padding is None else padding
    frame = ttk.Frame(root, padding=pad, style="TFrame")
    frame.pack(fill="both", expand=True)
    return frame


def divider(parent, pady=None):
    """A strong 2px horizontal rule, not a 1px hairline."""
    pad = t.SPACE[4] if pady is None else pady
    sep = tk.Frame(parent, height=2, bg=t.DIVIDER, bd=0, highlightthickness=0)
    sep.pack(fill="x", pady=pad)
    return sep


def heading(parent, text, scale="h3", muted=False, **pack_opts):
    """Styled section heading with consistent type scale.

    Uses ``tk.Label`` instead of ``ttk.Label`` so the background color is
    honored reliably on platforms where the clam theme ignores ``TLabel``
    background in padded areas.
    """
    from typing import Any

    font = t.font(scale)
    fg = t.TEXT_MUTED if muted else t.TEXT
    bg = pack_opts.pop("bg", t.BG)
    lbl = tk.Label(
        parent,
        text=text,
        font=font,
        fg=fg,
        bg=bg,
        anchor="w",
        bd=0,
        highlightthickness=0,
    )
    opts: dict[str, Any] = {"anchor": "w", "fill": "x"}
    opts.update(pack_opts)
    lbl.pack(**opts)
    return lbl


def field_row(parent, row, label_text, textvariable, *, label_width=None, entry_width=None, label_minsize=None):
    """One label+entry row on a 2-column grid with consistent rhythm.

    The label is a ``tk.Label`` (not ``ttk.Label``) so its background color
    always matches the parent frame on macOS. Column alignment is handled
    via ``grid_columnconfigure`` rather than a fixed label ``width``.

    Returns the created ``ttk.Entry``.
    """
    label = tk.Label(
        parent,
        text=label_text,
        fg=t.NEUTRAL[700],
        bg=t.BG,
        font=t.font("small"),
        anchor="w",
        bd=0,
        highlightthickness=0,
    )
    label.grid(row=row, column=0, sticky="w", padx=(0, t.SPACE[4]), pady=(0, t.SPACE[3]))

    if label_minsize:
        parent.grid_columnconfigure(0, minsize=label_minsize)
    if label_width:
        label.configure(width=label_width)

    entry = ttk.Entry(parent, textvariable=textvariable, font=t.font("body"))
    if entry_width:
        entry.configure(width=entry_width)
    entry.grid(row=row, column=1, sticky="ew", pady=(0, t.SPACE[3]))

    parent.grid_columnconfigure(1, weight=1)
    return entry


def window_header(parent, title, subtitle=None):
    """Standard top-of-window block: left-aligned title, optional muted
    subtitle, closed by a strong 2px rule. Replaces stacks of centered
    gray label boxes — hierarchy comes from type scale, not from boxes.

    Returns (title_label, subtitle_label_or_None).
    """
    title_lbl = tk.Label(parent, text=title, bg=t.BG, fg=t.TEXT,
                         font=t.font("h4"), anchor="w",
                         bd=0, highlightthickness=0)
    title_lbl.pack(fill="x")
    sub_lbl = None
    if subtitle is not None:
        sub_lbl = tk.Label(parent, text=subtitle, bg=t.BG, fg=t.TEXT_MUTED,
                           font=t.font("small"), anchor="w",
                           bd=0, highlightthickness=0)
        sub_lbl.pack(fill="x", pady=(t.SPACE[1], 0))
    rule = tk.Frame(parent, height=2, bg=t.DIVIDER, bd=0, highlightthickness=0)
    rule.pack(fill="x", pady=(t.SPACE[3], t.SPACE[4]))
    return title_lbl, sub_lbl


def data_list(parent, columns, height=12, selectmode: str = "browse"):
    """A styled ttk.Treeview for tabular lists.

    columns: list of (key, heading_text, width_px_or_None, anchor).
             width None = the column stretches to fill remaining space.
    Returns (container_frame, tree). Insert rows with add_row(tree, values).
    """
    container = ttk.Frame(parent, style="TFrame")
    keys = [c[0] for c in columns]
    tree = ttk.Treeview(
        container,
        columns=keys,
        show="headings",
        height=height,
        selectmode=selectmode,  # type: ignore[arg-type]
    )
    for key, head, width, anchor in columns:
        tree.heading(key, text=head, anchor=anchor)
        if width is None:
            tree.column(key, anchor=anchor, stretch=True)
        else:
            tree.column(key, width=width, minwidth=width, anchor=anchor, stretch=False)

    tree.tag_configure("odd", background=t.NEUTRAL[100])
    tree.tag_configure("even", background=t.BG)

    sb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)
    return container, tree


def add_row(tree, values):
    """Insert a row with automatic zebra striping."""
    idx = len(tree.get_children())
    tag = "odd" if idx % 2 else "even"
    return tree.insert("", "end", values=values, tags=(tag,))


def clear_rows(tree):
    tree.delete(*tree.get_children())


def status_bar(root, textvariable=None, text=""):
    """Bottom status bar: a 2px rule, then a left-aligned muted line.

    Use for hints and state instead of centered label boxes.
    Returns the label.
    """
    bar = tk.Frame(root, bg=t.BG, bd=0, highlightthickness=0)
    bar.pack(side="bottom", fill="x")
    rule = tk.Frame(bar, height=2, bg=t.DIVIDER, bd=0, highlightthickness=0)
    rule.pack(fill="x")
    lbl = tk.Label(bar, bg=t.BG, fg=t.TEXT_MUTED, font=t.font("small"),
                   anchor="w", padx=t.SPACE[6], pady=t.SPACE[2],
                   bd=0, highlightthickness=0)
    if textvariable is not None:
        lbl.configure(textvariable=textvariable)
    else:
        lbl.configure(text=text)
    lbl.pack(fill="x")
    return lbl


def button(parent, text, command=None, primary=False):
    """A themed button. primary=True is the solid accent fill — use for at
    most one action per window; everything else is secondary (outlined).
    """
    style = "Primary.TButton" if primary else "Secondary.TButton"
    if command is None:
        return ttk.Button(parent, text=text, style=style)
    return ttk.Button(parent, text=text, command=command, style=style)
