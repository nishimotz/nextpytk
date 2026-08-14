# -*- coding: utf-8 -*-
"""
Kizashi theme setup for ttk. Call apply_theme(root) once, right after
creating the root window and before building any widgets.
"""

import sys
import tkinter as tk
from tkinter import ttk

from . import tokens as t


def apply_theme(root: tk.Misc, tokens: t.ThemeTokens | None = None) -> ttk.Style:
    """Configure ttk styles from ThemeTokens. Call once on root."""
    tok = tokens or t.KIZASHI_LIGHT

    # Ensure FONT_FAMILY is resolved against the real font list now that Tk
    # is initialized.
    t.resolve_font_family()

    style = ttk.Style(root)

    # 'clam' is the only built-in theme that honors custom colors/borders
    # consistently across platforms.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    try:
        root.configure({"bg": tok.bg})
    except tk.TclError:
        pass

    # Apply the ::selection and keyboard focus colors to core tk widgets
    # (Text, Listbox, Entry). Option-database settings affect widgets created afterwards.
    root.option_add("*selectBackground", tok.selection_bg)
    root.option_add("*selectForeground", tok.selection_fg)
    root.option_add("*highlightColor", tok.focus)
    root.option_add("*Frame.background", tok.bg)
    root.option_add("*Label.background", tok.bg)
    root.option_add("*Label.foreground", tok.text)
    root.option_add("*Text.background", tok.surface)
    root.option_add("*Text.foreground", tok.text)
    root.option_add("*Text.insertBackground", tok.text)
    root.option_add("*Canvas.background", tok.surface)
    root.option_add("*Listbox.background", tok.bg)
    root.option_add("*Listbox.foreground", tok.text)

    # --- base -------------------------------------------------------------
    style.configure(".", background=tok.bg, foreground=tok.text, font=tok.font("body"))
    style.configure("TFrame", background=tok.bg)
    style.configure("Surface.TFrame", background=tok.surface)

    style.configure("TLabel", background=tok.bg, foreground=tok.text, font=tok.font("body"))
    style.configure("Heading.TLabel", font=tok.font("h3"))
    style.configure("Subheading.TLabel", font=tok.font("h5"))
    style.configure("Muted.TLabel", foreground=tok.text_muted, font=tok.font("body"))
    style.configure("FieldLabel.TLabel", foreground=tok.neutral.get(700, tok.text_muted), font=tok.font("small"))

    # --- divider (strong 2px rule) ----------------------------------------
    style.configure("Divider.TSeparator", background=tok.divider)

    # --- entries ------------------------------------------------------------
    style.configure(
        "TEntry",
        fieldbackground=tok.bg,
        foreground=tok.text,
        bordercolor=tok.divider,
        lightcolor=tok.divider,
        darkcolor=tok.divider,
        borderwidth=1,
        relief="solid",
        padding=(tok.space[2], tok.space[2] - 2),
        insertcolor=tok.text,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", tok.focus), ("hover", tok.neutral.get(600, tok.text_muted))],
        lightcolor=[("focus", tok.focus)],
        darkcolor=[("focus", tok.focus)],
    )

    # --- buttons ------------------------------------------------------------
    btn_padding = (tok.space[4], tok.space[3])
    style.configure(
        "TButton",
        font=tok.font("h5", weight="bold"),
        borderwidth=tok.space[2],
        relief="solid",
        padding=btn_padding,
        bordercolor=tok.neutral.get(500, tok.accent),
        anchor="center",
        width=0,
    )
    style.map(
        "TButton",
        bordercolor=[
            ("active", tok.neutral.get(600, tok.accent_hover)),
            ("pressed", tok.neutral.get(700, tok.accent_pressed)),
            ("focus", tok.focus),
        ],
    )
    style.configure(
        "Primary.TButton",
        font=tok.font("h5", weight="bold"),
        relief="solid",
        padding=btn_padding,
        background=tok.accent, foreground=tok.on_accent, bordercolor=tok.accent,
        borderwidth=tok.space[2],
        focuscolor=tok.on_accent,
        anchor="center",
        width=0,
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", tok.accent_pressed), ("active", tok.accent_hover),
                    ("focus", tok.accent)],
        foreground=[("focus", tok.on_accent)],
        bordercolor=[("pressed", tok.accent_pressed), ("active", tok.accent_hover),
                    ("focus", tok.accent)],
    )
    style.configure(
        "Secondary.TButton",
        font=tok.font("h5", weight="bold"),
        relief="solid",
        padding=btn_padding,
        background=tok.card, foreground=tok.text, bordercolor=tok.accent,
        borderwidth=tok.space[2],
        anchor="center",
        width=0,
    )
    style.map(
        "Secondary.TButton",
        background=[("pressed", tok.neutral.get(300, tok.surface)), ("active", tok.surface)],
        bordercolor=[
            ("active", tok.accent_hover),
            ("pressed", tok.accent_pressed),
            ("focus", tok.focus),
        ],
    )

    # --- notebook -----------------------------------------------------------
    style.configure("TNotebook", background=tok.bg, tabmargins=(tok.space[1], tok.space[1], tok.space[1], tok.space[1]))
    style.configure(
        "TNotebook.Tab",
        background=tok.neutral.get(200, tok.surface),
        foreground=tok.text,
        font=tok.font("small", weight="bold"),
        padding=(tok.space[3], tok.space[2]),
        uniform="tabs",
        anchor="w",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", tok.bg), ("active", tok.neutral.get(300, tok.surface))],
        foreground=[("selected", tok.text)],
        padding=[("selected", (tok.space[3], tok.space[4]))],
    )

    # --- check / radio ----------------------------------------------------
    check_radio_padding = (tok.space[4], tok.space[3])
    style.configure(
        "TCheckbutton",
        background=tok.bg,
        foreground=tok.text,
        font=tok.font("body"),
        focuscolor=tok.focus,
        padding=check_radio_padding,
        indicatormargin=(0, 0, tok.space[2], 0),
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
        background=tok.bg,
        foreground=tok.text,
        font=tok.font("body"),
        focuscolor=tok.focus,
        padding=check_radio_padding,
        indicatormargin=(0, 0, tok.space[2], 0),
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
        background=tok.bg,
        troughcolor=tok.surface,
        bordercolor=tok.accent,
        lightcolor=tok.accent,
        darkcolor=tok.accent,
        padding=(tok.space[1], tok.space[2]),
    )
    style.map(
        "TScale",
        bordercolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
        lightcolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
        darkcolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
    )

    # --- spinbox ------------------------------------------------------------
    style.configure(
        "TSpinbox",
        fieldbackground=tok.bg,
        foreground=tok.text,
        bordercolor=tok.divider,
        lightcolor=tok.divider,
        darkcolor=tok.divider,
        arrowcolor=tok.accent,
        borderwidth=1,
        relief="solid",
        padding=(tok.space[2], tok.space[2]),
        insertcolor=tok.text,
    )
    style.map(
        "TSpinbox",
        bordercolor=[("focus", tok.focus), ("hover", tok.neutral.get(600, tok.text_muted))],
        lightcolor=[("focus", tok.focus)],
        darkcolor=[("focus", tok.focus)],
        arrowcolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
    )

    # --- combobox -----------------------------------------------------------
    style.configure(
        "TCombobox",
        fieldbackground=tok.bg,
        foreground=tok.text,
        bordercolor=tok.divider,
        lightcolor=tok.divider,
        darkcolor=tok.divider,
        arrowcolor=tok.accent,
        borderwidth=1,
        relief="solid",
        padding=(tok.space[2], tok.space[2]),
        insertcolor=tok.text,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", tok.focus), ("hover", tok.neutral.get(600, tok.text_muted))],
        lightcolor=[("focus", tok.focus)],
        darkcolor=[("focus", tok.focus)],
        arrowcolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
        fieldbackground=[("readonly", tok.bg), ("active", tok.bg)],
        selectbackground=[("focus", tok.accent_ramp.get(200, tok.surface))],
        selectforeground=[("focus", tok.text)],
    )

    style.configure(
        "Readonly.TCombobox",
        fieldbackground=tok.bg,
        foreground=tok.text,
        bordercolor=tok.divider,
        lightcolor=tok.divider,
        darkcolor=tok.divider,
        arrowcolor=tok.accent,
        borderwidth=1,
        relief="solid",
        padding=(tok.space[2], tok.space[2]),
        insertcolor=tok.text,
    )
    style.map(
        "Readonly.TCombobox",
        bordercolor=[("focus", tok.focus), ("hover", tok.neutral.get(600, tok.text_muted))],
        lightcolor=[("focus", tok.focus)],
        darkcolor=[("focus", tok.focus)],
        arrowcolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
        fieldbackground=[("readonly", tok.bg), ("active", tok.bg)],
        selectbackground=[("focus", tok.accent_ramp.get(300, tok.surface))],
        selectforeground=[("focus", tok.text)],
        foreground=[("readonly", tok.text), ("active", tok.text)],
    )

    # --- progressbar --------------------------------------------------------
    style.configure(
        "TProgressbar",
        background=tok.accent,
        troughcolor=tok.surface,
        bordercolor=tok.divider,
        lightcolor=tok.divider,
        darkcolor=tok.divider,
        borderwidth=0,
    )
    style.map(
        "TProgressbar",
        background=[("active", tok.accent_hover)],
    )

    # --- scrollbar ----------------------------------------------------------
    style.configure(
        "TScrollbar",
        background=tok.bg,
        troughcolor=tok.surface,
        bordercolor=tok.accent,
        arrowcolor=tok.text,
        gripcount=0,
        borderwidth=0,
    )
    style.map(
        "TScrollbar",
        bordercolor=[("active", tok.accent_hover), ("pressed", tok.accent_pressed)],
        background=[("active", tok.neutral.get(100, tok.surface)), ("pressed", tok.neutral.get(200, tok.surface))],
        arrowcolor=[("active", tok.text), ("pressed", tok.text)],
    )

    # --- treeview -----------------------------------------------------------
    style.configure(
        "Treeview",
        background=tok.bg,
        foreground=tok.text,
        fieldbackground=tok.bg,
        font=tok.font("body"),
        rowheight=tok.space[8],
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=tok.surface,
        foreground=tok.text,
        font=tok.font("small", weight="bold"),
        borderwidth=0,
        relief="flat",
        padding=tok.space[2],
    )
    style.map(
        "Treeview",
        background=[("selected", tok.accent_ramp.get(100, tok.surface))],
        foreground=[("selected", tok.accent_ramp.get(700, tok.accent))],
    )

    return style


def _set_windows_dpi_aware():
    """Opt into system-DPI awareness before creating any Tk windows on Windows."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from typing import Any, cast
        _ctypes: Any = cast(Any, ctypes)
        windll: Any = _ctypes.windll
        try:
            awareness = ctypes.c_int(-4)
            windll.SetProcessDpiAwarenessContext(awareness)
            return
        except Exception:
            pass
        try:
            windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


def configure_window(root, title, min_width=380, min_height=260, resizable=True, tokens: t.ThemeTokens | None = None):
    """Apply consistent window chrome: background, title, sizing, margins."""
    tok = tokens or t.KIZASHI_LIGHT
    root.title(title)
    try:
        root.configure({"bg": tok.bg})
    except tk.TclError:
        pass
    root.minsize(min_width, min_height)
    root.resizable(resizable, resizable)

    if sys.platform.startswith("win"):
        try:
            import ctypes
            from typing import Any, cast
            _ctypes: Any = cast(Any, ctypes)
            windll: Any = _ctypes.windll
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = windll.user32.GetParent(root.winfo_id())
            # Enable dark titlebar if theme is dark
            is_dark = tok.name.endswith("-dark") or tok.bg.startswith(("#1", "#2", "#0"))
            value = ctypes.c_int(1 if is_dark else 0)
            windll.dwmapi.DwmSetWindowAttribute(
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
    subtitle. Hierarchy comes from type scale and spacing, not from boxes
    or divider lines (Kizashi design principle).

    Returns (title_label, subtitle_label_or_None).
    """
    header_bg = t.BG  # "#faf8f4" — same as page background
    
    # Title: Kizashi h4 with space-2 (16px) internal padding for consistent
    # background coverage. No bottom margin — spacing comes from subtitle.
    title_lbl = tk.Label(parent, text=title, bg=header_bg, fg=t.TEXT,
                         font=t.font("h4"), anchor="w",
                         bd=0, highlightthickness=0,
                         padx=t.SPACE[2], pady=t.SPACE[2])
    title_lbl.pack(fill="x")
    
    sub_lbl = None
    if subtitle is not None:
        # Kizashi small text with space-2 padding.
        # Top margin space-2 (16px) creates the gap from title.
        sub_lbl = tk.Label(parent, text=subtitle, bg=header_bg, fg=t.TEXT_MUTED,
                           font=t.font("small"), anchor="w",
                           bd=0, highlightthickness=0,
                           padx=t.SPACE[2], pady=t.SPACE[2])
        sub_lbl.pack(fill="x")
    
    # Add space-4 (32px) below the header to separate from the first section
    # (Kizashi section spacing principle).
    tk.Frame(parent, height=t.SPACE[4], bg=header_bg).pack(fill="x")
    
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

    tree.tag_configure("odd", background=t.BG)
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
    """Bottom status bar: a left-aligned muted line.

    Use for hints and state instead of centered label boxes.
    Hierarchy comes from spacing and typography (Kizashi principle).
    Returns the label.
    """
    bar = tk.Frame(root, bg=t.BG, bd=0, highlightthickness=0)
    bar.pack(side="bottom", fill="x")
    lbl = tk.Label(bar, bg=t.BG, fg=t.TEXT_MUTED, font=t.font("small"),
                   anchor="w", padx=t.SPACE[2], pady=t.SPACE[2],
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
